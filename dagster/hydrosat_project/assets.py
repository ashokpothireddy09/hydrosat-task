import json, datetime, io, os
import geopandas as gpd
import pandas as pd
from dagster import asset, DailyPartitionsDefinition, MetadataValue
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from shapely.geometry import box

PARTS = DailyPartitionsDefinition(start_date="2025-01-01")  # adjust

def _blob_client():
    cred = DefaultAzureCredential()
    account = os.getenv("AZURE_STORAGE_ACCOUNT")
    return BlobServiceClient(f"https://{account}.blob.core.windows.net", credential=cred)

@asset(
    partitions_def=PARTS,
    io_manager_key="io_manager",
    description="Daily per‑field metrics inside bounding box",
)
def field_metrics(context):
    date = datetime.date.fromisoformat(context.partition_key)
    bsc = _blob_client()
    cin = bsc.get_container_client("inputs")

    bbox = json.loads(cin.get_blob_client("bbox.json").download_blob().readall())
    fields_gj = cin.get_blob_client("fields.geojson").download_blob().readall()
    fields = gpd.read_file(io.BytesIO(fields_gj))

    # geometry filter
    roi = fields.clip(box(*bbox))

    # toy metric
    roi["value"] = roi.centroid.x * 0.0001 + roi.centroid.y * 0.0002 + (date.toordinal() % 7) * 0.01

    out_path = f"{date}/field_metrics.parquet"
    context.log.info(f"Uploading {out_path}")
    return context.resources.io_manager.handle_output(context, roi, out_path)  # saved via IO manager

    context.add_output_metadata({
        "rows": len(roi),
        "sample": MetadataValue.md(str(roi.head()))
    }) 