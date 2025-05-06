# Hydrosat Azure Challenge 🚀

# Hydrosat Geospatial Pipeline

A daily-partitioned geospatial data processing pipeline deployed on Azure Kubernetes Service using Dagster for orchestration.

## Overview

This project implements a data pipeline that:
- Processes geospatial data within defined bounding boxes
- Handles multiple field polygons with different planting dates
- Runs daily partitions with dependencies on previous days
- Stores results in Azure Blob Storage

## Project Structure
hydrosat-task/
├── README.md # Project overview (this file)
├── INSTRUCTIONS.md # Setup and deployment instructions
├── ARCHITECTURE.md # System architecture documentation
├── deploy.sh # One-click deployment script
├── terraform/ # Infrastructure as Code
│ ├── main.tf # Azure resources definition
│ ├── variables.tf # Configurable parameters
│ └── outputs.tf # Resource outputs
├── dagster/ # Dagster application
│ ├── Dockerfile # Container definition
│ ├── workspace.yaml # Dagster workspace config
│ ├── pyproject.toml # Python dependencies
│ └── hydrosat_project/ # Python code module
│ ├── init.py # Module initialization
│ ├── assets.py # Dagster assets definition
│ └── resources.py # Azure resources configuration
└── helm/ # Kubernetes deployment
└── dagster-values.yaml # Helm chart configuration

## Inputs

Upload once:

```bash
az storage blob upload-batch -s inputs/ -d inputs --account-name <storage>
```

* `bbox.json` – bounding rectangle `[xmin,ymin,xmax,ymax]`
* `fields.geojson` – polygons you drew via [https://geojson.io](https://geojson.io)

## Quick Start

1. Make sure prerequisites are installed (see INSTRUCTIONS.md)
2. Run the deployment script:


```bash
./deploy.sh               # takes ~15 min
# open dagster UI
```
3. Follow the instructions to access the Dagster UI
4. Materialize assets to process geospatial data

## Features

- **Daily Partitioning**: Process data in daily increments
- **Partition Dependencies**: Each day depends on the previous day's results
- **Geospatial Processing**: Filter fields by bounding box and planting date
- **Azure Integration**: Store inputs and outputs in Azure Blob Storage



## AI disclosure

Text, code, and the architecture diagram were drafted with **OpenAI o3** (ChatGPT) and reviewed by a human.

---

Enjoy ☀️ – PRs welcome!