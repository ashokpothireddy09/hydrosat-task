"""
Dagster entry‑point – wires assets + resources together.
"""

from dagster import Definitions

from .assets import hydrosat_data, dependent_asset
from .resources import azure_blob_resource, azure_pickle_io_manager

defs = Definitions(
    assets=[hydrosat_data, dependent_asset],
    resources={
        # Used directly inside the asset code
        "azure_blob": azure_blob_resource,
        # Default IO‑manager – handles persistence of ALL asset outputs
        "io_manager": azure_pickle_io_manager,
    },
)