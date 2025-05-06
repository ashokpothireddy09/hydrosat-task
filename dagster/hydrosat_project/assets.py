import datetime
import pandas as pd
import numpy as np
from shapely.geometry import Polygon, box, Point
import geopandas as gpd
import json
import io
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import random
from dagster import asset, AssetExecutionContext, DailyPartitionsDefinition, AssetDep, TimeWindowPartitionMapping

# Define the Azure Blob Storage container names
INPUT_CONTAINER = "inputs"
OUTPUT_CONTAINER = "outputs"

# Define the daily partitions
daily_partitions = DailyPartitionsDefinition(start_date="2024-01-01")

# Helper functions for synthetic data generation and zonal statistics

def generate_ndvi_raster(bbox, date, resolution=0.01):
    minx, miny, maxx, maxy = bbox.bounds
    width = int((maxx - minx) / resolution)
    height = int((maxy - miny) / resolution)
    x_coords = np.linspace(minx, maxx, width)
    y_coords = np.linspace(miny, maxy, height)
    date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
    day_of_year = date_obj.timetuple().tm_yday
    seasonal_factor = np.sin((day_of_year - 80) * 2 * np.pi / 365)
    seasonal_base = 0.2 + 0.3 * max(0, seasonal_factor)
    ndvi = np.zeros((height, width))
    for i in range(height):
        for j in range(width):
            x_rel = j / width
            y_rel = i / height
            if (x_rel - 0.5)**2 + (y_rel - 0.5)**2 < 0.1:
                land_factor = 0.8
                noise_level = 0.05
            elif x_rel < 0.3 and y_rel < 0.3:
                land_factor = 0.2
                noise_level = 0.05
            else:
                land_factor = 0.5 + 0.2 * np.sin(x_rel * 10) * np.cos(y_rel * 8)
                noise_level = 0.1
            noise = np.random.normal(0, noise_level)
            ndvi[i, j] = np.clip(seasonal_base * land_factor + noise, 0, 1)
    geotransform = (minx, resolution, 0, maxy, 0, -resolution)
    return ndvi, geotransform

def generate_soil_moisture_raster(bbox, date, ndvi_raster, resolution=0.01):
    height, width = ndvi_raster.shape
    date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
    day_of_year = date_obj.timetuple().tm_yday
    seasonal_factor = np.cos((day_of_year - 30) * 2 * np.pi / 365)
    seasonal_base = 0.3 + 0.2 * seasonal_factor
    soil_moisture = np.zeros((height, width))
    for i in range(height):
        for j in range(width):
            ndvi_factor = 0.5 + 0.5 * ndvi_raster[i, j]
            noise = np.random.normal(0, 0.08)
            soil_moisture[i, j] = np.clip(seasonal_base * ndvi_factor + noise, 0, 1)
    return soil_moisture

def generate_temperature_raster(bbox, date, resolution=0.01):
    minx, miny, maxx, maxy = bbox.bounds
    width = int((maxx - minx) / resolution)
    height = int((maxy - miny) / resolution)
    date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
    day_of_year = date_obj.timetuple().tm_yday
    seasonal_factor = np.sin((day_of_year - 80) * 2 * np.pi / 365)
    seasonal_base = 15 + 10 * seasonal_factor
    temperature = np.zeros((height, width))
    for i in range(height):
        for j in range(width):
            x_rel = j / width
            y_rel = i / height
            elevation_factor = -5 * ((x_rel - 0.7)**2 + (y_rel - 0.3)**2)
            noise = np.random.normal(0, 1.0)
            temperature[i, j] = seasonal_base + elevation_factor + noise
    return temperature

def zonal_statistics(raster, geotransform, polygon):
    x_origin, pixel_width, _, y_origin, _, pixel_height = geotransform
    pixel_height = abs(pixel_height)
    height, width = raster.shape
    minx, miny, maxx, maxy = polygon.bounds
    x_min_px = max(0, int((minx - x_origin) / pixel_width))
    y_min_px = max(0, int((y_origin - maxy) / pixel_height))
    x_max_px = min(width - 1, int((maxx - x_origin) / pixel_width))
    y_max_px = min(height - 1, int((y_origin - miny) / pixel_height))
    values = []
    for y in range(y_min_px, y_max_px + 1):
        for x in range(x_min_px, x_max_px + 1):
            real_x = x_origin + (x + 0.5) * pixel_width
            real_y = y_origin - (y + 0.5) * pixel_height
            if polygon.contains(Point(real_x, real_y)):
                values.append(raster[y, x])
    if values:
        return {
            'min': np.min(values),
            'max': np.max(values),
            'mean': np.mean(values),
            'std': np.std(values),
            'count': len(values)
        }
    else:
        return {'min': None, 'max': None, 'mean': None, 'std': None, 'count': 0}

def create_raster_plot(raster, title, cmap_name='viridis', vmin=None, vmax=None):
    plt.figure(figsize=(10, 8))
    if cmap_name == 'ndvi':
        cmap = LinearSegmentedColormap.from_list('ndvi', [
            (0.0, '#A16118'),
            (0.2, '#E6C78A'),
            (0.4, '#CEDB9C'),
            (0.7, '#50A747'),
            (1.0, '#1E5631')
        ])
    elif cmap_name == 'soil_moisture':
        cmap = LinearSegmentedColormap.from_list('soil', [
            (0.0, '#EBE3D0'),
            (0.3, '#C5B783'),
            (0.6, '#89A1C8'),
            (1.0, '#2F4F73')
        ])
    elif cmap_name == 'temperature':
        cmap = LinearSegmentedColormap.from_list('temp', [
            (0.0, '#0022FF'),
            (0.3, '#55AAFF'),
            (0.5, '#FFFFFF'),
            (0.7, '#FFAA55'),
            (1.0, '#FF0000')
        ])
    else:
        cmap = plt.get_cmap(cmap_name)
    im = plt.imshow(raster, cmap=cmap, vmin=vmin, vmax=vmax)
    plt.colorbar(im, label=title)
    plt.title(title)
    plt.axis('off')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf.getvalue()

def generate_random_field_polygons(bbox, num_fields=5, min_size=0.05, max_size=0.15):
    minx, miny, maxx, maxy = bbox.bounds
    width = maxx - minx
    height = maxy - miny
    fields = []
    crop_types = ["Corn", "Wheat", "Soybeans", "Barley", "Potatoes", "Alfalfa", "Rice"]
    start_date = datetime.datetime(2024, 1, 1)
    end_date = datetime.datetime(2024, 4, 30)
    date_range = (end_date - start_date).days
    for i in range(num_fields):
        center_x = minx + random.uniform(0.2, 0.8) * width
        center_y = miny + random.uniform(0.2, 0.8) * height
        field_size = random.uniform(min_size, max_size)
        field_width = field_size * width
        field_height = field_size * height
        angle = random.uniform(0, 90)
        corners = []
        for dx, dy in [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]:
            rotated_x = center_x + dx * field_width * np.cos(np.radians(angle)) - dy * field_height * np.sin(np.radians(angle))
            rotated_y = center_y + dx * field_width * np.sin(np.radians(angle)) + dy * field_height * np.cos(np.radians(angle))
            corners.append((rotated_x, rotated_y))
        planting_day = random.randint(0, date_range)
        planting_date = (start_date + datetime.timedelta(days=planting_day)).strftime("%Y-%m-%d")
        crop_type = random.choice(crop_types)
        fields.append({
            "id": f"field{i+1}",
            "name": f"{crop_type} Field {i+1}",
            "crop_type": crop_type,
            "planting_date": planting_date,
            "polygon": Polygon(corners)
        })
    return fields

@asset(
    partitions_def=daily_partitions,
    required_resource_keys={"azure_blob"}
)
def hydrosat_data(context: AssetExecutionContext):
    date = context.partition_key
    context.log.info(f"Processing data for date: {date}")
    
    # Try to use a bounding box from the input container if available
    bbox = box(12.0, 45.0, 12.5, 45.5)  # Default bounding box based on your bbox.json
    
    # Get blob clients for input and output containers
    input_client = context.resources.azure_blob.get_container_client(INPUT_CONTAINER)
    output_client = context.resources.azure_blob.get_container_client(OUTPUT_CONTAINER)
    
    # Try to load a bounding box from input container
    try:
        bbox_blob = input_client.download_blob("bbox.json").readall()
        bbox_coords = json.loads(bbox_blob)
        if len(bbox_coords) == 4:
            bbox = box(bbox_coords[0], bbox_coords[1], bbox_coords[2], bbox_coords[3])
            context.log.info(f"Loaded bounding box from storage: {bbox_coords}")
    except Exception as e:
        context.log.info(f"Using default bounding box: {str(e)}")
    
    # Try to load field polygons from a GeoJSON file if available
    try:
        geojson_blob = input_client.download_blob("fields.geojson").readall()
        fields_data = json.loads(geojson_blob)
        
        fields = []
        for feature in fields_data.get("features", []):
            field_id = str(feature.get("properties", {}).get("field_id", len(fields) + 1))
            coords = feature.get("geometry", {}).get("coordinates", [])[0]
            
            if coords:
                # Assume default planting date if not specified
                planting_date = "2024-01-15"
                crop_type = "Unknown"
                
                # Create field with polygon from GeoJSON
                fields.append({
                    "id": f"field{field_id}",
                    "name": f"Field {field_id}",
                    "crop_type": crop_type,
                    "planting_date": planting_date,
                    "polygon": Polygon(coords)
                })
        
        if fields:
            context.log.info(f"Loaded {len(fields)} fields from GeoJSON")
    except Exception as e:
        context.log.info(f"Attempting to load field definitions from JSON: {str(e)}")
        
        # Try the original approach - load from field_definitions.json
        fields_filename = "field_definitions.json"
        try:
            blob_data = input_client.download_blob(fields_filename).readall()
            fields_json = json.loads(blob_data)
            fields = []
            for field in fields_json:
                field["polygon"] = Polygon(field["polygon_coords"])
                del field["polygon_coords"]
                fields.append(field)
            context.log.info(f"Loaded {len(fields)} fields from field definitions")
        except Exception as e:
            context.log.info(f"Generating new field definitions: {str(e)}")
            fields = generate_random_field_polygons(bbox, num_fields=8)
            fields_json = []
            for field in fields:
                field_copy = field.copy()
                field_copy["polygon_coords"] = list(field["polygon"].exterior.coords)
                del field_copy["polygon"]
                fields_json.append(field_copy)
            # Save field definitions to input container
            input_client.upload_blob(name=fields_filename, data=json.dumps(fields_json), overwrite=True)
    
    gdf_fields = gpd.GeoDataFrame(fields, geometry='polygon')
    gdf_fields['intersects'] = gdf_fields.geometry.intersects(bbox)
    gdf_fields = gdf_fields[gdf_fields['intersects']]
    gdf_fields = gdf_fields[gdf_fields['planting_date'] <= date]
    
    if gdf_fields.empty:
        context.log.info("No fields to process for this date")
        return pd.DataFrame()
    
    resolution = 0.01
    ndvi_raster, geotransform = generate_ndvi_raster(bbox, date, resolution)
    soil_moisture_raster = generate_soil_moisture_raster(bbox, date, ndvi_raster, resolution)
    temperature_raster = generate_temperature_raster(bbox, date, resolution)
    
    results = []
    for idx, field in gdf_fields.iterrows():
        days_since_planting = (datetime.datetime.strptime(date, "%Y-%m-%d") - datetime.datetime.strptime(field['planting_date'], "%Y-%m-%d")).days
        ndvi_stats = zonal_statistics(ndvi_raster, geotransform, field['polygon'])
        soil_moisture_stats = zonal_statistics(soil_moisture_raster, geotransform, field['polygon'])
        temperature_stats = zonal_statistics(temperature_raster, geotransform, field['polygon'])
        
        result = {
            "field_id": field['id'],
            "field_name": field['name'],
            "crop_type": field['crop_type'],
            "date": date,
            "days_since_planting": days_since_planting,
            "ndvi_mean": ndvi_stats['mean'],
            "ndvi_min": ndvi_stats['min'],
            "ndvi_max": ndvi_stats['max'],
            "ndvi_std": ndvi_stats['std'],
            "soil_moisture_mean": soil_moisture_stats['mean'],
            "soil_moisture_min": soil_moisture_stats['min'],
            "soil_moisture_max": soil_moisture_stats['max'],
            "soil_moisture_std": soil_moisture_stats['std'],
            "temperature_mean": temperature_stats['mean'],
            "temperature_min": temperature_stats['min'],
            "temperature_max": temperature_stats['max'],
            "temperature_std": temperature_stats['std'],
        }
        results.append(result)
    
    df_results = pd.DataFrame(results)
    if not df_results.empty:
        # Save results to output container
        csv_filename = f"hydrosat_data_{date}.csv"
        csv_content = df_results.to_csv(index=False)
        output_client.upload_blob(name=csv_filename, data=csv_content, overwrite=True)
        
        json_filename = f"hydrosat_data_{date}.json"
        json_content = df_results.to_json(orient="records")
        output_client.upload_blob(name=json_filename, data=json_content, overwrite=True)
        
        # Save visualizations to output container
        ndvi_plot = create_raster_plot(ndvi_raster, f"NDVI - {date}", cmap_name='ndvi', vmin=0, vmax=1)
        output_client.upload_blob(name=f"plots/ndvi_{date}.png", data=ndvi_plot, overwrite=True)
        
        soil_plot = create_raster_plot(soil_moisture_raster, f"Soil Moisture - {date}", cmap_name='soil_moisture', vmin=0, vmax=1)
        output_client.upload_blob(name=f"plots/soil_moisture_{date}.png", data=soil_plot, overwrite=True)
        
        temp_plot = create_raster_plot(temperature_raster, f"Temperature (\u00b0C) - {date}", cmap_name='temperature', vmin=0, vmax=30)
        output_client.upload_blob(name=f"plots/temperature_{date}.png", data=temp_plot, overwrite=True)
        
        context.log.info(f"Saved results and visualizations to Azure Blob Storage for {date}")
    
    return df_results

@asset(
    partitions_def=daily_partitions,
    deps=[AssetDep(hydrosat_data, partition_mapping=TimeWindowPartitionMapping(start_offset=-1, end_offset=-1))],
    required_resource_keys={"azure_blob"}
)
def dependent_asset(context: AssetExecutionContext):
    """
    Process dependent asset that uses the previous day's hydrosat_data.
    Loads the data directly from blob storage instead of using the IO manager.
    """
    current_date = context.partition_key
    prev_date = (datetime.datetime.strptime(current_date, "%Y-%m-%d") - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    context.log.info(f"Processing dependent asset for date: {current_date}, using data from: {prev_date}")
    
    # Get blob client for output container
    output_client = context.resources.azure_blob.get_container_client(OUTPUT_CONTAINER)
    
    try:
        # Load current day's data directly from the output container
        current_filename = f"hydrosat_data_{current_date}.csv"
        current_blob_data = output_client.download_blob(current_filename).readall()
        current_data = pd.read_csv(pd.io.common.BytesIO(current_blob_data))
        
        # Load previous day's data directly from the output container
        prev_filename = f"hydrosat_data_{prev_date}.csv"
        prev_blob_data = output_client.download_blob(prev_filename).readall()
        prev_data = pd.read_csv(pd.io.common.BytesIO(prev_blob_data))
        
        if current_data.empty or prev_data.empty:
            context.log.info("Missing data for processing")
            return pd.DataFrame()
        
        # Merge current and previous data
        merged_data = pd.merge(current_data, prev_data, on=["field_id", "field_name", "crop_type"], suffixes=("", "_prev"))
        
        if not merged_data.empty:
            # Calculate changes
            for metric in ['ndvi_mean', 'soil_moisture_mean', 'temperature_mean']:
                merged_data[f'{metric}_change'] = merged_data[metric] - merged_data[f'{metric}_prev']
                if metric != 'temperature_mean':
                    merged_data[f'{metric}_pct_change'] = ((merged_data[metric] - merged_data[f'{metric}_prev']) / merged_data[f'{metric}_prev'] * 100).fillna(0)
            
            merged_data['growth_rate'] = merged_data['ndvi_mean_change'] / merged_data['days_since_planting']
            
            # Save results to output container
            output_filename = f"hydrosat_changes_{current_date}.csv"
            output_content = merged_data.to_csv(index=False)
            output_client.upload_blob(name=output_filename, data=output_content, overwrite=True)
            
            # Generate and save visualizations for each field
            for field_id in merged_data['field_id'].unique():
                field_data = merged_data[merged_data['field_id'] == field_id].iloc[0]
                
                plt.figure(figsize=(12, 8))
                plt.suptitle(f"Field Analysis: {field_data['field_name']} ({field_data['crop_type']})", fontsize=16)
                plt.figtext(0.5, 0.92, f"Date: {current_date} | Days since planting: {field_data['days_since_planting']}", ha='center', fontsize=12)
                
                plt.subplot(2, 2, 1)
                plt.bar(['Previous', 'Current'], [field_data['ndvi_mean_prev'], field_data['ndvi_mean']], color=['lightgreen', 'darkgreen'])
                plt.title('NDVI Mean')
                plt.ylim(0, 1)
                
                plt.subplot(2, 2, 2)
                plt.bar(['Previous', 'Current'], [field_data['soil_moisture_mean_prev'], field_data['soil_moisture_mean']], color=['lightblue', 'darkblue'])
                plt.title('Soil Moisture Mean')
                plt.ylim(0, 1)
                
                plt.subplot(2, 2, 3)
                plt.bar(['Previous', 'Current'], [field_data['temperature_mean_prev'], field_data['temperature_mean']], color=['orange', 'red'])
                plt.title('Temperature Mean (\u00b0C)')
                
                plt.subplot(2, 2, 4)
                changes = [field_data['ndvi_mean_change'], field_data['soil_moisture_mean_change'], field_data['temperature_mean_change']]
                colors = ['green', 'blue', 'red']
                plt.bar(['NDVI', 'Soil Moisture', 'Temperature'], changes, color=colors)
                plt.title('Day-over-Day Changes')
                plt.axhline(y=0, color='k', linestyle='-', alpha=0.3)
                
                plot_filename = f"plots/field_summary_{field_id}_{current_date}.png"
                buf = io.BytesIO()
                plt.tight_layout(rect=[0, 0, 1, 0.9])
                plt.savefig(buf, format='png', dpi=100)
                plt.close()
                buf.seek(0)
                output_client.upload_blob(name=plot_filename, data=buf.getvalue(), overwrite=True)
            
            context.log.info(f"Saved change analysis and visualizations to Azure Blob Storage")
            return merged_data
        else:
            context.log.info("No matching fields between current and previous data")
            return pd.DataFrame()
    except Exception as e:
        context.log.error(f"Error processing data: {str(e)}")
        return pd.DataFrame()