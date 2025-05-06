# 🌍 Hydrosat Geospatial Analytics Pipeline

A production-ready geospatial data processing pipeline deployed on Azure Kubernetes Service with Dagster orchestration, designed for daily partitioned satellite imagery analysis of agricultural fields.


## 🔍 Overview

This pipeline performs daily processing of geospatial data for agricultural fields, generating critical vegetation, soil moisture, and temperature metrics. It implements a production-grade system that:

- **Processes synthetic satellite data** within a predefined geographic region
- **Analyzes agricultural fields** based on their geometry and planting dates
- **Tracks daily changes** with inter-day dependencies for trend analysis
- **Generates visualizations** for quick insights into field performance
- **Stores everything** in Azure Blob Storage for downstream applications

The system demonstrates key concepts of modern cloud-native data engineering: Infrastructure as Code, containerization, orchestration, and reproducible data science.

## 🏗️ Architecture

![Architecture Diagram](https://i.imgur.com/example.png)

The pipeline leverages Azure's managed Kubernetes service alongside Dagster orchestration to provide a scalable, maintainable platform for geospatial analytics. See the [ARCHITECTURE.md](ARCHITECTURE.md) document for detailed technical information.

## 📁 Project Structure

```
hydrosat-task/
├── README.md              # Project overview (this file)
├── INSTRUCTIONS.md        # Setup and deployment instructions  
├── ARCHITECTURE.md        # System architecture documentation
├── deploy.sh              # One-click deployment script
├── terraform/             # Infrastructure as Code
│   ├── main.tf            # Azure resources definition
│   ├── variables.tf       # Configurable parameters
│   └── outputs.tf         # Resource outputs
├── dagster/               # Dagster application
│   ├── Dockerfile         # Container definition
│   ├── workspace.yaml     # Dagster workspace config
│   ├── pyproject.toml     # Python dependencies
│   └── hydrosat_project/  # Python code module
│       ├── __init__.py    # Module initialization
│       ├── assets.py      # Dagster assets definition
│       └── resources.py   # Azure resources configuration
└── helm/                  # Kubernetes deployment
    └── dagster-values.yaml # Helm chart configuration
```

## 🛠️ Technologies

- **Infrastructure**: Azure Kubernetes Service, Azure Container Registry, Azure Blob Storage
- **Data Processing**: Python, NumPy, Pandas, GeoPandas, Shapely
- **Visualization**: Matplotlib, custom colormaps
- **Orchestration**: Dagster with daily partitioning
- **DevOps**: Terraform, Helm, Docker, Kubernetes
- **Storage**: Azure Blob Storage (S3-compatible)

## 🏃‍♂️ Quick Start

### Prerequisites

Ensure you have installed:
- Azure CLI
- Terraform
- kubectl
- Helm

See [INSTRUCTIONS.md](INSTRUCTIONS.md) for detailed installation steps.

### Deployment

```bash
# One-click deployment of all infrastructure and application
./deploy.sh

# Access the Dagster UI
kubectl -n dagster port-forward svc/dagster-dagster-webserver 8080:80
```

Then open http://localhost:8080 in your browser.

## 📊 Features

### 1. Geospatial Data Processing

- **Fixed Bounding Box**: Process data for a specific geographic region
- **Field Geometry Analysis**: Calculate metrics for field shapes
- **Planting Date Awareness**: Track growth relative to planting dates

### 2. Advanced Metrics

- **NDVI Analysis**: Track vegetation health and growth
- **Soil Moisture Monitoring**: Assess water content in soil
- **Temperature Tracking**: Monitor thermal conditions
- **Statistical Aggregation**: Calculate min, max, mean, and std deviation per field

### 3. Time Series Capabilities

- **Daily Processing**: Partitioned by date for consistent analysis
- **Change Detection**: Calculate day-over-day changes in all metrics
- **Temporal Dependencies**: Each day builds on previous results

### 4. Visualization

- **Raster Visualizations**: Color-coded maps of NDVI, soil moisture, and temperature
- **Field Summaries**: Per-field visualizations showing trends and changes
- **Custom Colormaps**: Domain-specific colormaps for agricultural interpretation

### 5. Cloud-Native Design

- **Kubernetes Deployment**: Scalable, containerized processing
- **Infrastructure as Code**: Reproducible infrastructure with Terraform
- **Orchestration**: Robust pipeline management with Dagster
- **Storage Integration**: Seamless Azure Blob Storage integration

## 💻 Usage

1. **Deploy the Pipeline**: Follow the deployment instructions
2. **Materialize Assets**: Use Dagster UI to run the pipeline for specific dates
3. **Analyze Results**: View outputs in Azure Blob Storage or Dagster UI

### Example Workflow

```bash
# Deploy infrastructure
./deploy.sh

# Run pipeline through Dagster UI (or CLI)
dagster asset materialize --asset-selection hydrosat_data --partition-key 2025-05-05
dagster asset materialize --asset-selection dependent_asset --partition-key 2025-05-05
```

## 📋 Output Data

The pipeline generates:

- **CSV/JSON Files**: Field metrics for each day
- **Change Analysis**: Day-over-day changes in all metrics
- **Visualizations**: PNG files for all metrics and fields
- **Statistical Summaries**: Aggregated statistics per field

## 🔄 Development

To modify the pipeline:

1. Update the Python code in `dagster/hydrosat_project/`
2. Rebuild the Docker image
3. Update the Helm deployment

See [INSTRUCTIONS.md](INSTRUCTIONS.md) for detailed development workflows.

## 📜 License

This project is open-source and available under the MIT License.

## 🙏 Acknowledgements

- **Hydrosat** for the challenge inspiration
- **Dagster** team for the orchestration framework
- **Azure** for the cloud infrastructure
- **OpenAI o3** (ChatGPT) for assistance with documentation

---

Designed and implemented for the Hydrosat Azure Challenge, 2025. PRs and feedback welcome!