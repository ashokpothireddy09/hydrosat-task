"""
Reusable Dagster resources for the Hydrosat project.

1. `azure_blob_resource`
   ↳ Gives every asset an authenticated `BlobServiceClient` based on
     • AZURE_STORAGE_CONNECTION_STRING   – or –
     • AZURE_STORAGE_ACCOUNT  +  AZURE_STORAGE_KEY

2. `azure_pickle_io_manager`
   ↳ Persists / loads Dagster asset outputs as pickled objects in the
     **outputs** container, so downstream assets running in a *different*
     Kubernetes pod can still read yesterday's DataFrame.

     Written path pattern:
     az://outputs/dagster/storage/<asset_key>/<partition_key>/<idx>.pkl
"""

import os
from dagster import resource, io_manager, UPathIOManager
from azure.storage.blob import BlobServiceClient
from adlfs import AzureBlobFileSystem
from upath import UPath


# ────────────────────────────────────────────────────────────────────────────────
#  1. Blob client resource  ──────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────────────
@resource(
    description="Azure Blob Storage client – uses connection string or account/key.",
)
def azure_blob_resource(_):
    # Prefer full connection‑string (single var, recommended by Azure portal)
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if conn_str:
        return BlobServiceClient.from_connection_string(conn_str)

    # Fallback to account + key
    account = os.getenv("AZURE_STORAGE_ACCOUNT")
    key     = os.getenv("AZURE_STORAGE_KEY")
    if account and key:
        return BlobServiceClient(
            f"https://{account}.blob.core.windows.net", credential=key
        )

    # Nothing set → hard‑fail with clear message
    raise RuntimeError(
        "Azure credentials missing.  Please set either:\n"
        "  • AZURE_STORAGE_CONNECTION_STRING   or\n"
        "  • AZURE_STORAGE_ACCOUNT and AZURE_STORAGE_KEY"
    )


# ────────────────────────────────────────────────────────────────────────────────
#  2. IO‑manager that pickles to Blob Storage  ──────────────────────────────────
# ────────────────────────────────────────────────────────────────────────────────
OUTPUT_CONTAINER = "outputs"


@io_manager(required_resource_keys={"azure_blob"})
def azure_pickle_io_manager(init_context):
    """
    Serialises Dagster asset values with `pickle` and stores them in the
    <outputs> container.  When a downstream asset asks for an input that lives
    in another pod / day, the IO‑manager downloads & un‑pickles it.
    """
    account_name = init_context.resources.azure_blob.account_name
    key          = os.getenv("AZURE_STORAGE_KEY")   # needed by adlfs

    if not key:   # fail early – otherwise you'd get a cryptic 403 later on
        raise RuntimeError("AZURE_STORAGE_KEY must be set for the IO‑manager")

    fs = AzureBlobFileSystem(
        account_name=account_name,
        account_key=key,
        container_name=OUTPUT_CONTAINER,
    )

    # UPathIOManager handles the (de)serialisation mechanics for us
    return UPathIOManager(base_path=UPath("/", fs))