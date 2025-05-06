# hydrosat_project/assets.py
import datetime
import pandas as pd
import numpy as np
import json
from shapely.geometry import Polygon, box, Point
import geopandas as gpd
from dagster import asset, AssetExecutionContext, DailyPartitionsDefinition, AssetDep, TimeWindowPartitionMapping
import matplotlib.pyplot as plt
import io
from matplotlib.colors import LinearSegmentedColormap
import random

# Define the Azure Blob Storage container name
CONTAINER_NAME = "data"

# Define the daily partitions
daily_partitions = DailyPartitionsDefinition(start_date="2024-01-01")

def generate_ndvi_raster(bbox, date, resolution=0.01):
    """
    Generate a synthetic NDVI raster for the given bounding box and date.
    
    Args:
        bbox: The bounding box to generate data for
        date: The date string in YYYY-MM-DD format
        resolution: The spatial resolution of the raster
        
    Returns:
        A 2D numpy array of NDVI values and the geotransform information
    """
    # Extract bounding box coordinates
    minx, miny, maxx, maxy = bbox.bounds
    
    # Calculate grid dimensions
    width = int((maxx - minx) / resolution)
    height = int((maxy - miny) / resolution)
    
    # Create coordinate grids
    x_coords = np.linspace(minx, maxx, width)
    y_coords = np.linspace(miny, maxy, height)
    
    # Parse the date
    date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
    
    # Calculate day of year (0-365)
    day_of_year = date_obj.timetuple().tm_yday
    
    # Create base NDVI pattern (seasonal variation)
    # Northern hemisphere seasonal pattern with peak in summer
    seasonal_factor = np.sin((day_of_year - 80) * 2 * np.pi / 365)
    seasonal_base = 0.2 + 0.3 * max(0, seasonal_factor)
    
    # Create spatial variation (simulate different land cover types)
    ndvi = np.zeros((height, width))
    
    for i in range(height):
        for j in range(width):
            # Create spatial patterns
            x_rel = j / width
            y_rel = i / height
            
            # Simulate different land cover types
            if (x_rel - 0.5)**2 + (y_rel - 0.5)**2 < 0.1:  # Central area - forest
                land_factor = 0.8
                noise_level = 0.05
            elif x_rel < 0.3 and y_rel < 0.3:  # Urban area
                land_factor = 0.2
                noise_level = 0.05
            else:  # Agricultural areas with some variation
                land_factor = 0.5 + 0.2 * np.sin(x_rel * 10) * np.cos(y_rel * 8)
                noise_level = 0.1
            
            # Add some random noise
            noise = np.random.normal(0, noise_level)
            
            # Combine factors
            ndvi[i, j] = np.clip(seasonal_base * land_factor + noise, 0, 1)
    
    # Create geotransform information (for GIS compatibility)
    geotransform = (minx, resolution, 0, maxy, 0, -resolution)
    
    return ndvi, geotransform

def generate_soil_moisture_raster(bbox, date, ndvi_raster, resolution=0.01):
    """
    Generate a synthetic soil moisture raster based on NDVI and date.
    
    Args:
        bbox: The bounding box to generate data for
        date: The date string in YYYY-MM-DD format
        ndvi_raster: The NDVI raster to base soil moisture on
        resolution: The spatial resolution of the raster
        
    Returns:
        A 2D numpy array of soil moisture values (0-1 scale)
    """
    # Extract dimensions from NDVI raster
    height, width = ndvi_raster.shape
    
    # Parse the date
    date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
    
    # Calculate day of year (0-365)
    day_of_year = date_obj.timetuple().tm_yday
    
    # Create base soil moisture pattern (seasonal variation)
    # Higher in spring and fall, lower in summer and winter
    seasonal_factor = np.cos((day_of_year - 30) * 2 * np.pi / 365)
    seasonal_base = 0.3 + 0.2 * seasonal_factor
    
    # Create soil moisture raster
    soil_moisture = np.zeros((height, width))
    
    for i in range(height):
        for j in range(width):
            # Soil moisture is correlated with NDVI but not perfectly
            ndvi_factor = 0.5 + 0.5 * ndvi_raster[i, j]
            
            # Add some random noise (soil type variation)
            noise = np.random.normal(0, 0.08)
            
            # Combine factors
            soil_moisture[i, j] = np.clip(seasonal_base * ndvi_factor + noise, 0, 1)
    
    return soil_moisture

def generate_temperature_raster(bbox, date, resolution=0.01):
    """
    Generate a synthetic temperature raster for the given bounding box and date.
    
    Args:
        bbox: The bounding box to generate data for
        date: The date string in YYYY-MM-DD format
        resolution: The spatial resolution of the raster
        
    Returns:
        A 2D numpy array of temperature values (in degrees Celsius)
    """
    # Extract bounding box coordinates
    minx, miny, maxx, maxy = bbox.bounds
    
    # Calculate grid dimensions
    width = int((maxx - minx) / resolution)
    height = int((maxy - miny) / resolution)
    
    # Parse the date
    date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
    
    # Calculate day of year (0-365)
    day_of_year = date_obj.timetuple().tm_yday
    
    # Create base temperature pattern (seasonal variation)
    # Northern hemisphere seasonal pattern with peak in summer
    seasonal_factor = np.sin((day_of_year - 80) * 2 * np.pi / 365)
    seasonal_base = 15 + 10 * seasonal_factor  # Base temperature varies from 5°C to 25°C
    
    # Create spatial variation (simulate elevation and other effects)
    temperature = np.zeros((height, width))
    
    for i in range(height):
        for j in range(width):
            # Create spatial patterns
            x_rel = j / width
            y_rel = i / height
            
            # Simulate elevation effect (higher elevations are cooler)
            elevation_factor = -5 * ((x_rel - 0.7)**2 + (y_rel - 0.3)**2)
            
            # Add some random noise
            noise = np.random.normal(0, 1.0)
            
            # Combine factors
            temperature[i, j] = seasonal_base + elevation_factor + noise
    
    return temperature

def zonal_statistics(raster, geotransform, polygon):
    """
    Calculate zonal statistics for a polygon on a raster.
    
    Args:
        raster: 2D numpy array containing raster values
        geotransform: Geotransform tuple (x_origin, pixel_width, 0, y_origin, 0, -pixel_height)
        polygon: Shapely polygon to calculate statistics for
        
    Returns:
        Dictionary of statistics (min, max, mean, std)
    """
    # Extract geotransform parameters
    x_origin, pixel_width, _, y_origin, _, pixel_height = geotransform
    pixel_height = abs(pixel_height)  # Make sure it's positive
    
    # Get raster dimensions
    height, width = raster.shape
    
    # Get polygon bounds
    minx, miny, maxx, maxy = polygon.bounds
    
    # Convert bounds to pixel coordinates
    x_min_px = max(0, int((minx - x_origin) / pixel_width))
    y_min_px = max(0, int((y_origin - maxy) / pixel_height))
    x_max_px = min(width - 1, int((maxx - x_origin) / pixel_width))
    y_max_px = min(height - 1, int((y_origin - miny) / pixel_height))
    
    # Initialize list to store values within polygon
    values = []
    
    # Iterate through pixels in bounding box
    for y in range(y_min_px, y_max_px + 1):
        for x in range(x_min_px, x_max_px + 1):
            # Calculate real-world coordinates of pixel center
            real_x = x_origin + (x + 0.5) * pixel_width
            real_y = y_origin - (y + 0.5) * pixel_height
            
            # Check if pixel center is within polygon
            if polygon.contains(Point(real_x, real_y)):
                values.append(raster[y, x])
    
    # Calculate statistics
    if values:
        return {
            'min': np.min(values),
            'max': np.max(values),
            'mean': np.mean(values),
            'std': np.std(values),
            'count': len(values)
        }
    else:
        return {
            'min': None,
            'max': None,
            'mean': None,
            'std': None,
            'count': 0
        }

def create_raster_plot(raster, title, cmap_name='viridis', vmin=None, vmax=None):
    """
    Create a plot of a raster dataset and return it as bytes.
    
    Args:
        raster: 2D numpy array of raster values
        title: Title for the plot
        cmap_name: Name of the colormap to use
        vmin: Minimum value for colormap scaling
        vmax: Maximum value for colormap scaling
        
    Returns:
        Bytes object containing the PNG image
    """
    plt.figure(figsize=(10, 8))
    
    # Choose appropriate colormap based on data type
    if cmap_name == 'ndvi':
        # Custom NDVI colormap (brown to green)
        cmap = LinearSegmentedColormap.from_list('ndvi', [
            (0.0, '#A16118'),  # Brown for low NDVI
            (0.2, '#E6C78A'),  # Tan
            (0.4, '#CEDB9C'),  # Light green
            (0.7, '#50A747'),  # Medium green
            (1.0, '#1E5631')   # Dark green for high NDVI
        ])
    elif cmap_name == 'soil_moisture':
        # Custom soil moisture colormap (light to dark blue)
        cmap = LinearSegmentedColormap.from_list('soil', [
            (0.0, '#EBE3D0'),  # Light tan for dry soil
            (0.3, '#C5B783'),  # Tan
            (0.6, '#89A1C8'),  # Light blue
            (1.0, '#2F4F73')   # Dark blue for wet soil
        ])
    elif cmap_name == 'temperature':
        # Custom temperature colormap (blue to red)
        cmap = LinearSegmentedColormap.from_list('temp', [
            (0.0, '#0022FF'),  # Blue for cold
            (0.3, '#55AAFF'),  # Light blue
            (0.5, '#FFFFFF'),  # White
            (0.7, '#FFAA55'),  # Light red
            (1.0, '#FF0000')   # Red for hot
        ])
    else:
        cmap = plt.get_cmap(cmap_name)
    
    # Plot the raster
    im = plt.imshow(raster, cmap=cmap, vmin=vmin, vmax=vmax)
    plt.colorbar(im, label=title)
    plt.title(title)
    plt.axis('off')
    
    # Save plot to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    
    return buf.getvalue()

def generate_random_field_polygons(bbox, num_fields=5, min_size=0.05, max_size=0.15):
    """
    Generate random field polygons within a bounding box.
    
    Args:
        bbox: Shapely box representing the bounding box
        num_fields: Number of fields to generate
        min_size: Minimum field size as a fraction of the bounding box
        max_size: Maximum field size as a fraction of the bounding box
        
    Returns:
        List of dictionaries containing field information
    """
    minx, miny, maxx, maxy = bbox.bounds
    width = maxx - minx
    height = maxy - miny
    
    fields = []
    crop_types = ["Corn", "Wheat", "Soybeans", "Barley", "Potatoes", "Alfalfa", "Rice"]
    
    # Generate random planting dates between Jan 1 and Apr 30
    start_date = datetime.datetime(2024, 1, 1)
    end_date = datetime.datetime(2024, 4, 30)
    date_range = (end_date - start_date).days
    
    for i in range(num_fields):
        # Random field center
        center_x = minx + random.uniform(0.2, 0.8) * width
        center_y = miny + random.uniform(0.2, 0.8) * height
        
        # Random field size
        field_size = random.uniform(min_size, max_size)
        field_width = field_size * width
        field_height = field_size * height
        
        # Random rotation angle
        angle = random.uniform(0, 90)
        
        # Create field corners
        corners = []
        for dx, dy in [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]:
            # Rotate point around center
            rotated_x = center_x + dx * field_width * np.cos(np.radians(angle)) - dy * field_height * np.sin(np.radians(angle))
            rotated_y = center_y + dx * field_width * np.sin(np.radians(angle)) + dy * field_height * np.cos(np.radians(angle))
            corners.append((rotated_x, rotated_y))
        
        # Random planting date
        planting_day = random.randint(0, date_range)
        planting_date = (start_date + datetime.timedelta(days=planting_day)).strftime("%Y-%m-%d")
        
        # Random crop type
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
def hydrosat_data(context: AssetExecutionContext, azure_blob):
    """
    Processes geospatial data within a bounding box for multiple fields.
    Each field has a planting date, and processing only occurs for fields
    after their planting date.
    
    This asset:
    1. Defines a bounding box for processing
    2. Generates or loads field polygons within the bounding box
    3. Simulates remote sensing data (NDVI, soil moisture, temperature)
    4. Calculates zonal statistics for each field
    5. Stores results and visualizations in Azure Blob Storage
    """
    date = context.partition_key
    context.log.info(f"Processing data for date: {date}")
    
    # Define the bounding box (processing extent)
    # Using coordinates in a projected coordinate system (example: somewhere in Europe)
    bbox = box(10.0, 45.0, 11.0, 46.0)
    
    # Try to load fields from a previous run, or generate new ones
    blob_client = azure_blob.get_container_client(CONTAINER_NAME)
    fields_filename = "field_definitions.json"
    
    try:
        # Try to load existing field definitions
        blob_data = blob_client.download_blob(fields_filename).readall()
        fields_json = json.loads(blob_data)
        fields = []
        for field in fields_json:
            # Reconstruct the polygon from coordinates
            field["polygon"] = Polygon(field["polygon_coords"])
            del field["polygon_coords"]  # Remove the coordinates as we now have the polygon
            fields.append(field)
        context.log.info(f"Loaded {len(fields)} fields from storage")
    except Exception as e:
        context.log.info(f"Generating new field definitions: {str(e)}")
        # Generate random fields
        fields = generate_random_field_polygons(bbox, num_fields=8)
        
        # Save field definitions for future runs
        fields_json = []
        for field in fields:
            field_copy = field.copy()
            field_copy["polygon_coords"] = list(field["polygon"].exterior.coords)
            del field_copy["polygon"]  # Remove the polygon as it's not JSON serializable
            fields_json.append(field_copy)
        
        blob_client.upload_blob(name=fields_filename, data=json.dumps(fields_json), overwrite=True)
    
    # Convert to GeoDataFrame for spatial operations
    gdf_fields = gpd.GeoDataFrame(fields, geometry='polygon')
    
    # Filter fields that are within the bounding box
    gdf_fields['intersects'] = gdf_fields.geometry.intersects(bbox)
    gdf_fields = gdf_fields[gdf_fields['intersects']]
    
    # Filter fields that have been planted by the current date
    gdf_fields = gdf_fields[gdf_fields['planting_date'] <= date]
    
    if gdf_fields.empty:
        context.log.info("No fields to process for this date")
        return pd.DataFrame()
    
    # Generate synthetic remote sensing data for the bounding box
    resolution = 0.01  # 0.01 degrees, approximately 1km
    
    # Generate NDVI raster
    ndvi_raster, geotransform = generate_ndvi_raster(bbox, date, resolution)
    
    # Generate soil moisture raster based on NDVI
    soil_moisture_raster = generate_soil_moisture_raster(bbox, date, ndvi_raster, resolution)
    
    # Generate temperature raster
    temperature_raster = generate_temperature_raster(bbox, date, resolution)
    
    # Calculate zonal statistics for each field
    results = []
    for idx, field in gdf_fields.iterrows():
        # Calculate days since planting
        days_since_planting = (datetime.datetime.strptime(date, "%Y-%m-%d") - 
                              datetime.datetime.strptime(field['planting_date'], "%Y-%m-%d")).days
        
        # Calculate zonal statistics for each raster
        ndvi_stats = zonal_statistics(ndvi_raster, geotransform, field['polygon'])
        soil_moisture_stats = zonal_statistics(soil_moisture_raster, geotransform, field['polygon'])
        temperature_stats = zonal_statistics(temperature_raster, geotransform, field['polygon'])
        
        # Combine results
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
    
    # Create DataFrame from results
    df_results = pd.DataFrame(results)
    
    # Save results to Azure Blob Storage
    if not df_results.empty:
        # Save as CSV
        csv_filename = f"hydrosat_data_{date}.csv"
        csv_content = df_results.to_csv(index=False)
        blob_client.upload_blob(name=csv_filename, data=csv_content, overwrite=True)
        
        # Save as JSON
        json_filename = f"hydrosat_data_{date}.json"
        json_content = df_results.to_json(orient="records")
        blob_client.upload_blob(name=json_filename, data=json_content, overwrite=True)
        
        # Create and save visualizations
        # NDVI visualization
        ndvi_plot = create_raster_plot(ndvi_raster, f"NDVI - {date}", cmap_name='ndvi', vmin=0, vmax=1)
        blob_client.upload_blob(name=f"plots/ndvi_{date}.png", data=ndvi_plot, overwrite=True)
        
        # Soil moisture visualization
        soil_plot = create_raster_plot(soil_moisture_raster, f"Soil Moisture - {date}", 
                                      cmap_name='soil_moisture', vmin=0, vmax=1)
        blob_client.upload_blob(name=f"plots/soil_moisture_{date}.png", data=soil_plot, overwrite=True)
        
        # Temperature visualization
        temp_plot = create_raster_plot(temperature_raster, f"Temperature (°C) - {date}", 
                                      cmap_name='temperature', vmin=0, vmax=30)
        blob_client.upload_blob(name=f"plots/temperature_{date}.png", data=temp_plot, overwrite=True)
        
        context.log.info(f"Saved results and visualizations to Azure Blob Storage for {date}")
    
    return df_results

@asset(
    partitions_def=daily_partitions,
    deps=[AssetDep(hydrosat_data, partition_mapping=TimeWindowPartitionMapping(start_offset=-1, end_offset=-1))],
    required_resource_keys={"azure_blob"}
)
def dependent_asset(context: AssetExecutionContext, azure_blob):
    """
    This asset depends on the previous day's hydrosat_data.
    It calculates day-over-day changes in field metrics and generates
    trend visualizations.
    
    This asset:
    1. Retrieves the current day's data from the upstream asset
    2. Loads the previous day's data from storage
    3. Calculates changes in metrics (NDVI, soil moisture, temperature)
    4. Generates trend visualizations
    5. Stores results and visualizations in Azure Blob Storage
    """
    current_date = context.partition_key
    
    # Calculate previous date
    prev_date = (datetime.datetime.strptime(current_date, "%Y-%m-%d") - 
                datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    context.log.info(f"Processing dependent asset for date: {current_date}, using data from: {prev_date}")
    
    # Get the current day's data from the upstream asset
    current_data = context.asset_values[hydrosat_data]
    
    if current_data.empty:
        context.log.info("No current data available for processing")
        return pd.DataFrame()
    
    # Read previous day's data from Azure Blob Storage
    blob_client = azure_blob.get_container_client(CONTAINER_NAME)
    prev_filename = f"hydrosat_data_{prev_date}.csv"
    
    try:
        # Download blob content
        blob_data = blob_client.download_blob(prev_filename).readall()
        prev_data = pd.read_csv(pd.io.common.BytesIO(blob_data))
        
        # Merge current and previous data
        merged_data = pd.merge(
            current_data, 
            prev_data,
            on=["field_id", "field_name", "crop_type"],
            suffixes=('', '_prev')
        )
        
        # Calculate changes
        if not merged_data.empty:
            # Calculate changes for all metrics
            for metric in ['ndvi_mean', 'soil_moisture_mean', 'temperature_mean']:
                merged_data[f'{metric}_change'] = merged_data[metric] - merged_data[f'{metric}_prev']
                
                # Calculate percent change for applicable metrics
                if metric != 'temperature_mean':  # Percent change doesn't make sense for temperature
                    merged_data[f'{metric}_pct_change'] = (
                        (merged_data[metric] - merged_data[f'{metric}_prev']) / 
                        merged_data[f'{metric}_prev'] * 100
                    ).fillna(0)  # Handle division by zero
            
            # Calculate growth rate (for vegetation indices)
            merged_data['growth_rate'] = merged_data['ndvi_mean_change'] / merged_data['days_since_planting']
            
            # Save results
            output_filename = f"hydrosat_changes_{current_date}.csv"
            output_content = merged_data.to_csv(index=False)
            blob_client.upload_blob(name=output_filename, data=output_content, overwrite=True)
            
            # Generate trend visualization for each field
            for field_id in merged_data['field_id'].unique():
                field_data = merged_data[merged_data['field_id'] == field_id].iloc[0]
                
                # Create a summary plot for this field
                plt.figure(figsize=(12, 8))
                
                # Field information
                plt.suptitle(f"Field Analysis: {field_data['field_name']} ({field_data['crop_type']})", 
                            fontsize=16)
                plt.figtext(0.5, 0.92, f"Date: {current_date} | Days since planting: {field_data['days_since_planting']}", 
                           ha='center', fontsize=12)
                
                # NDVI subplot
                plt.subplot(2, 2, 1)
                plt.bar(['Previous', 'Current'], 
                       [field_data['ndvi_mean_prev'], field_data['ndvi_mean']], 
                       color=['lightgreen', 'darkgreen'])
                plt.title('NDVI Mean')
                plt.ylim(0, 1)
                
                # Soil moisture subplot
                plt.subplot(2, 2, 2)
                plt.bar(['Previous', 'Current'], 
                       [field_data['soil_moisture_mean_prev'], field_data['soil_moisture_mean']], 
                       color=['lightblue', 'darkblue'])
                plt.title('Soil Moisture Mean')
                plt.ylim(0, 1)
                
                # Temperature subplot
                plt.subplot(2, 2, 3)
                plt.bar(['Previous', 'Current'], 
                       [field_data['temperature_mean_prev'], field_data['temperature_mean']], 
                       color=['orange', 'red'])
                plt.title('Temperature Mean (°C)')
                
                # Changes subplot
                plt.subplot(2, 2, 4)
                changes = [
                    field_data['ndvi_mean_change'], 
                    field_data['soil_moisture_mean_change'], 
                    field_data['temperature_mean_change']
                ]
                colors = ['green', 'blue', 'red']
                plt.bar(['NDVI', 'Soil Moisture', 'Temperature'], changes, color=colors)
                plt.title('Day-over-Day Changes')
                plt.axhline(y=0, color='k', linestyle='-', alpha=0.3)
                
                # Save the plot
                plot_filename = f"plots/field_summary_{field_id}_{current_date}.png"
                buf = io.BytesIO()
                plt.tight_layout(rect=[0, 0, 1, 0.9])
                plt.savefig(buf, format='png', dpi=100)
                plt.close()
                buf.seek(0)
                blob_client.upload_blob(name=plot_filename, data=buf.getvalue(), overwrite=True)
            
            context.log.info(f"Saved change analysis and visualizations to Azure Blob Storage")
            return merged_data
        else:
            context.log.info("No matching fields between current and previous data")
            return pd.DataFrame()
    
    except Exception as e:
        context.log.error(f"Error processing previous day's data: {str(e)}")
        # For the first day or if previous data doesn't exist, return just the current data
        return current_data
