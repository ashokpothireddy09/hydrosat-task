from dagster import resource
from dagster_azure.adls2 import adls2_parquet_io_manager
import os

@resource
def adls2_parquet_io_manager():
    """Parquet IOManager wired to the account passed via env var."""
    account = os.getenv("AZURE_STORAGE_ACCOUNT")
    return adls2_parquet_io_manager.configured(
        {"storage_account": account, "container": "outputs"}
    ) 