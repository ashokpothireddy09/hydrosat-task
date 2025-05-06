"""
Dagster entry‑point: wires up the assets defined in assets.py with
the Azure‑Blob resource defined in resources.py.
"""

from dagster import Definitions

# Assets that actually exist
from .assets import hydrosat_data, dependent_asset

# Resource that gives the assets an authenticated blob‑client
from .resources import azure_blob_resource

# Register everything with Dagster
defs = Definitions(
    assets=[
        hydrosat_data,
        dependent_asset,
    ],
    resources={
        # key must match required_resource_keys in @asset decorators
        "azure_blob": azure_blob_resource,
    },
)
