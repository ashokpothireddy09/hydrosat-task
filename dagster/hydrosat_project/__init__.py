from dagster import Definitions
from .assets import field_metrics
from .resources import adls2_parquet_io_manager

defs = Definitions(
    assets=[field_metrics],
    resources={"io_manager": adls2_parquet_io_manager},
) 