# hydrosat_project/assets.py
import datetime
import io
import json
import random
from matplotlib.colors import LinearSegmentedColormap

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon, box

from dagster import (
    AssetExecutionContext,
    AssetIn,
    DailyPartitionsDefinition,
    TimeWindowPartitionMapping,
    asset,
)

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------
CONTAINER_NAME = "data"  # Azure Blob container
daily_partitions = DailyPartitionsDefinition(start_date="2024-01-01")

# ---------------------------------------------------------------------
# Synthetic‑data helper functions (unchanged)
# ---------------------------------------------------------------------


def generate_ndvi_raster(bbox, date, resolution: float = 0.01):
    minx, miny, maxx, maxy = bbox.bounds
    width = int((maxx - minx) / resolution)
    height = int((maxy - miny) / resolution)

    date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
    day_of_year = date_obj.timetuple().tm_yday

    seasonal_factor = np.sin((day_of_year - 80) * 2 * np.pi / 365)
    seasonal_base = 0.2 + 0.3 * max(0, seasonal_factor)

    ndvi = np.zeros((height, width))
    for i in range(height):
        for j in range(width):
            x_rel, y_rel = j / width, i / height
            if (x_rel - 0.5) ** 2 + (y_rel - 0.5) ** 2 < 0.1:
                land_factor, noise_level = 0.8, 0.05
            elif x_rel < 0.3 and y_rel < 0.3:
                land_factor, noise_level = 0.2, 0.05
            else:
                land_factor = 0.5 + 0.2 * np.sin(x_rel * 10) * np.cos(y_rel * 8)
                noise_level = 0.1
            noise = np.random.normal(0, noise_level)
            ndvi[i, j] = np.clip(seasonal_base * land_factor + noise, 0, 1)

    geotransform = (minx, resolution, 0, maxy, 0, -resolution)
    return ndvi, geotransform


def generate_soil_moisture_raster(bbox, date, ndvi_raster, resolution: float = 0.01):
    height, width = ndvi_raster.shape
    day_of_year = datetime.datetime.strptime(date, "%Y-%m-%d").timetuple().tm_yday
    seasonal_factor = np.cos((day_of_year - 30) * 2 * np.pi / 365)
    seasonal_base = 0.3 + 0.2 * seasonal_factor

    soil = np.zeros((height, width))
    for i in range(height):
        for j in range(width):
            ndvi_factor = 0.5 + 0.5 * ndvi_raster[i, j]
            noise = np.random.normal(0, 0.08)
            soil[i, j] = np.clip(seasonal_base * ndvi_factor + noise, 0, 1)
    return soil


def generate_temperature_raster(bbox, date, resolution: float = 0.01):
    minx, miny, maxx, maxy = bbox.bounds
    width = int((maxx - minx) / resolution)
    height = int((maxy - miny) / resolution)

    day_of_year = datetime.datetime.strptime(date, "%Y-%m-%d").timetuple().tm_yday
    seasonal_factor = np.sin((day_of_year - 80) * 2 * np.pi / 365)
    seasonal_base = 15 + 10 * seasonal_factor

    temp = np.zeros((height, width))
    for i in range(height):
        for j in range(width):
            x_rel, y_rel = j / width, i / height
            elevation_factor = -5 * ((x_rel - 0.7) ** 2 + (y_rel - 0.3) ** 2)
            noise = np.random.normal(0, 1.0)
            temp[i, j] = seasonal_base + elevation_factor + noise
    return temp


def zonal_statistics(raster, geotransform, polygon):
    x_origin, pixel_w, _, y_origin, _, pixel_h = geotransform
    pixel_h = abs(pixel_h)
    h, w = raster.shape
    minx, miny, maxx, maxy = polygon.bounds

    x_min = max(0, int((minx - x_origin) / pixel_w))
    y_min = max(0, int((y_origin - maxy) / pixel_h))
    x_max = min(w - 1, int((maxx - x_origin) / pixel_w))
    y_max = min(h - 1, int((y_origin - miny) / pixel_h))

    vals = [
        raster[y, x]
        for y in range(y_min, y_max + 1)
        for x in range(x_min, x_max + 1)
        if polygon.contains(
            Point(x_origin + (x + 0.5) * pixel_w, y_origin - (y + 0.5) * pixel_h)
        )
    ]
    return (
        {
            "min": np.min(vals),
            "max": np.max(vals),
            "mean": np.mean(vals),
            "std": np.std(vals),
            "count": len(vals),
        }
        if vals
        else {"min": None, "max": None, "mean": None, "std": None, "count": 0}
    )


def create_raster_plot(raster, title, cmap_name="viridis", vmin=None, vmax=None):
    plt.figure(figsize=(10, 8))
    if cmap_name == "ndvi":
        cmap = LinearSegmentedColormap.from_list(
            "ndvi",
            [
                (0.0, "#A16118"),
                (0.2, "#E6C78A"),
                (0.4, "#CEDB9C"),
                (0.7, "#50A747"),
                (1.0, "#1E5631"),
            ],
        )
    elif cmap_name == "soil_moisture":
        cmap = LinearSegmentedColormap.from_list(
            "soil",
            [
                (0.0, "#EBE3D0"),
                (0.3, "#C5B783"),
                (0.6, "#89A1C8"),
                (1.0, "#2F4F73"),
            ],
        )
    elif cmap_name == "temperature":
        cmap = LinearSegmentedColormap.from_list(
            "temp",
            [
                (0.0, "#0022FF"),
                (0.3, "#55AAFF"),
                (0.5, "#FFFFFF"),
                (0.7, "#FFAA55"),
                (1.0, "#FF0000"),
            ],
        )
    else:
        cmap = plt.get_cmap(cmap_name)

    im = plt.imshow(raster, cmap=cmap, vmin=vmin, vmax=vmax)
    plt.colorbar(im, label=title)
    plt.title(title)
    plt.axis("off")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close()
    buf.seek(0)
    return buf.getvalue()


def generate_random_field_polygons(bbox, num_fields=5, min_size=0.05, max_size=0.15):
    minx, miny, maxx, maxy = bbox.bounds
    width, height = maxx - minx, maxy - miny
    fields, crops = [], [
        "Corn",
        "Wheat",
        "Soybeans",
        "Barley",
        "Potatoes",
        "Alfalfa",
        "Rice",
    ]

    start, end = datetime.datetime(2024, 1, 1), datetime.datetime(2024, 4, 30)
    for i in range(num_fields):
        cx = minx + random.uniform(0.2, 0.8) * width
        cy = miny + random.uniform(0.2, 0.8) * height
        size = random.uniform(min_size, max_size)
        fw, fh = size * width, size * height
        angle = random.uniform(0, 90)

        corners = [
            (
                cx
                + dx * fw * np.cos(np.radians(angle))
                - dy * fh * np.sin(np.radians(angle)),
                cy
                + dx * fw * np.sin(np.radians(angle))
                + dy * fh * np.cos(np.radians(angle)),
            )
            for dx, dy in [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
        ]
        planting_date = (start + datetime.timedelta(days=random.randint(0, (end - start).days))).strftime(
            "%Y-%m-%d"
        )
        crop = random.choice(crops)
        fields.append(
            {
                "id": f"field{i+1}",
                "name": f"{crop} Field {i+1}",
                "crop_type": crop,
                "planting_date": planting_date,
                "polygon": Polygon(corners),
            }
        )
    return fields


# ---------------------------------------------------------------------
# Asset definitions
# ---------------------------------------------------------------------


@asset(partitions_def=daily_partitions, required_resource_keys={"azure_blob"})
def hydrosat_data(context: AssetExecutionContext):
    """
    Generate daily synthetic NDVI, soil‑moisture & temperature rasters for a
    bounding box, compute zonal stats for each field and upload results +
    plots to Azure Blob.
    """
    azure_blob = context.resources.azure_blob
    date = context.partition_key
    context.log.info(f"Processing date: {date}")

    bbox = box(10.0, 45.0, 11.0, 46.0)
    blob_client = azure_blob.get_container_client(CONTAINER_NAME)

    # 1) field polygons (load or create)
    try:
        data = blob_client.download_blob("field_definitions.json").readall()
        fields_json = json.loads(data)
        fields = [
            {**fld, "polygon": Polygon(fld["polygon_coords"])} for fld in fields_json
        ]
        context.log.info(f"Loaded {len(fields)} fields")
    except Exception:
        fields = generate_random_field_polygons(bbox, num_fields=8)
        blob_client.upload_blob(
            "field_definitions.json",
            data=json.dumps(
                [
                    {**fld, "polygon_coords": list(fld["polygon"].exterior.coords)}
                    | {"polygon": None}
                    for fld in fields
                ]
            ),
            overwrite=True,
        )

    gdf = gpd.GeoDataFrame(fields, geometry="polygon")
    gdf = gdf[gdf.geometry.intersects(bbox) & (gdf["planting_date"] <= date)]

    if gdf.empty:
        context.log.info("No fields to process")
        return pd.DataFrame()

    # 2) rasters
    ndvi, geo = generate_ndvi_raster(bbox, date)
    soil = generate_soil_moisture_raster(bbox, date, ndvi)
    temp = generate_temperature_raster(bbox, date)

    # 3) zonal stats
    rows = []
    for _, row in gdf.iterrows():
        days = (
            datetime.datetime.strptime(date, "%Y-%m-%d")
            - datetime.datetime.strptime(row["planting_date"], "%Y-%m-%d")
        ).days
        rows.append(
            {
                "field_id": row["id"],
                "field_name": row["name"],
                "crop_type": row["crop_type"],
                "date": date,
                "days_since_planting": days,
                **{f"ndvi_{k}": v for k, v in zonal_statistics(ndvi, geo, row["polygon"]).items()},
                **{
                    f"soil_moisture_{k}": v
                    for k, v in zonal_statistics(soil, geo, row["polygon"]).items()
                },
                **{
                    f"temperature_{k}": v
                    for k, v in zonal_statistics(temp, geo, row["polygon"]).items()
                },
            }
        )
    df = pd.DataFrame(rows)

    # 4) persist
    blob_client.upload_blob(
        f"hydrosat_data_{date}.csv", df.to_csv(index=False), overwrite=True
    )
    blob_client.upload_blob(
        f"hydrosat_data_{date}.json", df.to_json(orient="records"), overwrite=True
    )
    blob_client.upload_blob(
        f"plots/ndvi_{date}.png",
        create_raster_plot(ndvi, f"NDVI {date}", "ndvi", 0, 1),
        overwrite=True,
    )
    blob_client.upload_blob(
        f"plots/soil_{date}.png",
        create_raster_plot(soil, f"Soil Moisture {date}", "soil_moisture", 0, 1),
        overwrite=True,
    )
    blob_client.upload_blob(
        f"plots/temp_{date}.png",
        create_raster_plot(temp, f"Temperature {date}", "temperature", 0, 30),
        overwrite=True,
    )
    context.log.info("Daily data & plots saved")
    return df


@asset(
    partitions_def=daily_partitions,
    ins={
        "hydrosat_data": AssetIn(
            partition_mapping=TimeWindowPartitionMapping(start_offset=-1, end_offset=-1)
        )
    },
    required_resource_keys={"azure_blob"},
)
def dependent_asset(
    context: AssetExecutionContext,
    hydrosat_data: pd.DataFrame,
):
    """
    Day‑over‑day deltas for NDVI / soil‑moisture / temperature + plots.
    """
    azure_blob = context.resources.azure_blob
    if hydrosat_data.empty:
        context.log.info("No upstream data → skipping")
        return pd.DataFrame()

    date = context.partition_key
    prev_date = (
        datetime.datetime.strptime(date, "%Y-%m-%d") - datetime.timedelta(days=1)
    ).strftime("%Y-%m-%d")
    blob_client = azure_blob.get_container_client(CONTAINER_NAME)

    try:
        prev = pd.read_csv(
            io.BytesIO(blob_client.download_blob(f"hydrosat_data_{prev_date}.csv").readall())
        )
    except Exception:
        context.log.info("No previous‑day data; nothing to compare")
        return hydrosat_data

    merged = hydrosat_data.merge(
        prev, on=["field_id", "field_name", "crop_type"], suffixes=("", "_prev")
    )
    if merged.empty:
        context.log.info("No matching fields between days")
        return pd.DataFrame()

    for metric in ["ndvi_mean", "soil_moisture_mean", "temperature_mean"]:
        merged[f"{metric}_change"] = merged[metric] - merged[f"{metric}_prev"]
        if metric != "temperature_mean":
            merged[f"{metric}_pct_change"] = (
                (merged[metric] - merged[f"{metric}_prev"]) / merged[f"{metric}_prev"] * 100
            ).fillna(0)
    merged["growth_rate"] = merged["ndvi_mean_change"] / merged["days_since_planting"]

    blob_client.upload_blob(
        f"hydrosat_changes_{date}.csv", merged.to_csv(index=False), overwrite=True
    )
    context.log.info("Change‑analysis CSV saved")

    # quick per‑field bar plots
    for fid in merged["field_id"].unique():
        row = merged[merged["field_id"] == fid].iloc[0]
        plt.figure(figsize=(10, 6))
        plt.suptitle(f"{row['field_name']} – {date}")
        plt.subplot(2, 2, 1)
        plt.bar(["prev", "now"], [row["ndvi_mean_prev"], row["ndvi_mean"]], color=["#98fb98", "#006400"])
        plt.title("NDVI")
        plt.ylim(0, 1)

        plt.subplot(2, 2, 2)
        plt.bar(
            ["prev", "now"],
            [row["soil_moisture_mean_prev"], row["soil_moisture_mean"]],
            color=["#add8e6", "#00008b"],
        )
        plt.title("Soil Moisture")
        plt.ylim(0, 1)

        plt.subplot(2, 2, 3)
        plt.bar(
            ["prev", "now"],
            [row["temperature_mean_prev"], row["temperature_mean"]],
            color=["#ffa07a", "#8b0000"],
        )
        plt.title("Temperature (°C)")

        plt.subplot(2, 2, 4)
        plt.bar(
            ["NDVI", "Soil", "Temp"],
            [row["ndvi_mean_change"], row["soil_moisture_mean_change"], row["temperature_mean_change"]],
            color=["#006400", "#00008b", "#8b0000"],
        )
        plt.axhline(0, color="k", lw=0.5)
        plt.title("Δ day‑over‑day")

        buf = io.BytesIO()
        plt.tight_layout(rect=[0, 0, 1, 0.93])
        plt.savefig(buf, format="png", dpi=100)
        plt.close()
        buf.seek(0)
        blob_client.upload_blob(
            f"plots/field_summary_{fid}_{date}.png", buf.getvalue(), overwrite=True
        )

    context.log.info("Plots & change analysis saved")
    return merged
