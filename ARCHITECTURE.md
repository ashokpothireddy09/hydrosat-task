# System Architecture

This document explains the architecture of the Hydrosat geospatial data processing pipeline.

## Overview

The system processes geospatial data for agricultural fields on a daily basis, calculating metrics like vegetation indices, soil moisture, and temperature. Each day's processing depends on the previous day's results, enabling trend analysis over time.

## Infrastructure Components

![Architecture Diagram](https://i.imgur.com/example.png)

### Azure Kubernetes Service (AKS)
- Hosts the Dagster orchestration platform
- Manages containerized workloads
- Provides scalability for data processing

### Azure Container Registry (ACR)
- Stores Docker container images
- Securely manages and deploys the Dagster application container

### Azure Blob Storage
- Stores input data (bounding boxes, field polygons)
- Stores output data (processed metrics, visualizations)
- Acts as a data lake for the pipeline

### Dagster
- Orchestrates the data pipeline
- Manages assets, dependencies, and schedules
- Provides a UI for monitoring and triggering runs

## Data Flow

The pipeline follows this sequence:

1. **Data Ingestion**
   - Bounding box definition loaded from Azure Blob Storage
   - Field polygons with planting dates loaded from Azure Blob Storage

2. **Field Filtering**
   - Fields are filtered based on intersection with the bounding box
   - Only fields that have been planted by the current date are processed

3. **Data Processing**
   - For each field, synthetic remote sensing data is generated
   - Metrics are calculated for each field (NDVI, soil moisture, temperature)
   - Results are aggregated per field

4. **Data Storage**
   - Processed results are stored in Azure Blob Storage
   - Both CSV and JSON formats are generated
   - Visualizations are stored as PNG files

5. **Change Analysis**
   - The dependent asset compares current day's data with previous day
   - Calculates day-over-day changes in metrics
   - Generates trend visualizations

## Dagster Assets

The pipeline consists of two main Dagster assets:

### 1. hydrosat_data
- **Purpose**: Primary data processing asset
- **Partitioning**: Daily partitions
- **Inputs**: Bounding box, field polygons
- **Processing**: 
  - Filters fields by bounding box intersection
  - Filters fields by planting date
  - Generates synthetic remote sensing data
  - Calculates field-specific metrics
- **Outputs**: CSV/JSON files with field metrics

### 2. dependent_asset
- **Purpose**: Trend analysis asset
- **Partitioning**: Daily partitions
- **Dependencies**: Previous day's hydrosat_data
- **Processing**:
  - Compares current metrics with previous day
  - Calculates changes in NDVI, soil moisture, temperature
  - Generates trend visualizations
- **Outputs**: CSV files with change metrics, PNG visualizations

## Daily Partitioning

The pipeline uses Dagster's partitioning system to:

1. Process data in daily increments
2. Create dependencies between days (each day depends on the previous)
3. Allow for backfilling of historical data if needed

## Geospatial Processing

For each daily partition, the pipeline:

1. Filters fields that intersect with the bounding box
2. Processes only fields that have been planted by the current date
3. Generates synthetic remote sensing data (NDVI, soil moisture, temperature)
4. Calculates zonal statistics for each field
5. Produces visualizations of the data

## Security

The architecture implements several security measures:

1. Private Azure Container Registry for secure image storage
2. Azure Kubernetes Service with proper RBAC
3. Private storage access through managed identities
4. Secure secrets management

## Scaling Considerations

The architecture can scale in several ways:

1. AKS can add nodes to handle increased processing load
2. Dagster can run multiple materializations in parallel
3. Storage can expand automatically as data volumes grow

This architecture provides a robust foundation for geospatial data processing that can be extended with additional Azure services as needs evolve.
