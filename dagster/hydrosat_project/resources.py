"""
Reusable Dagster resources for the Hydrosat project.
Provides azure_blob_resource that can use either connection string or account+key.
"""

from dagster import resource
from azure.storage.blob import BlobServiceClient
import os


@resource(
    description="Azure Blob Storage client – uses connection string or account/key credentials.",
)
def azure_blob_resource(init_context):
    """
    Returns an Azure Blob Storage client configured from environment variables.
    Supports either connection string or account+key method.
    """
    # Try connection string method first (already in your Helm values)
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        return BlobServiceClient.from_connection_string(conn_str)

    # Fall back to account + key method
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT")
    account_key = os.getenv("AZURE_STORAGE_KEY")
    if account_name and account_key:
        return BlobServiceClient(
            f"https://{account_name}.blob.core.windows.net", 
            credential=account_key
        )

    # No credentials found - clear error message
    raise RuntimeError(
        "Please set either AZURE_STORAGE_CONNECTION_STRING "
        "or both AZURE_STORAGE_ACCOUNT and AZURE_STORAGE_KEY!"
    )
