"""
Reusable Dagster resources for the Hydrosat project.
The main one is `azure_blob_resource`, which returns a Blob‑storage
client configured from environment variables injected into the pod.
"""

from dagster import resource
from dagster_azure.blob import (
    AzureBlobStorageResource,
    AzureBlobStorageKeyCredential,
)
import os


@resource(
    description="Azure Blob Storage client – credentials are taken from "
                "AZURE_STORAGE_ACCOUNT and AZURE_STORAGE_KEY env‑vars.",
)
def azure_blob_resource(init_context):
    account_name = os.getenv("AZURE_STORAGE_ACCOUNT")
    account_key = os.getenv("AZURE_STORAGE_KEY")

    if not account_name or not account_key:
        raise RuntimeError(
            "Environment variables AZURE_STORAGE_ACCOUNT and "
            "AZURE_STORAGE_KEY must be set!"
        )

    return AzureBlobStorageResource(
        storage_account=account_name,
        credential=AzureBlobStorageKeyCredential(account_key),
    )
