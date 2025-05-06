INSTRUCTIONS.md
text
# Setup and Deployment Instructions

This document provides detailed instructions for setting up and deploying the Hydrosat geospatial pipeline.

## Prerequisites

Before starting, ensure you have the following installed:

1. **Azure CLI** - For interacting with Azure resources
Install on Ubuntu/Debian
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

Install on macOS
brew install azure-cli

text

2. **Terraform** - For provisioning infrastructure
Install on Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y gnupg software-properties-common
wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt-get update && sudo apt-get install terraform

Install on macOS
brew install terraform

text

3. **kubectl** - For managing Kubernetes resources
Install on Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y kubectl

Install on macOS
brew install kubectl

text

4. **Helm** - For deploying Dagster to Kubernetes
Install on Ubuntu/Debian
curl https://baltocdn.com/helm/signing.asc | sudo apt-key add -
sudo apt-get install apt-transport-https --yes
echo "deb https://baltocdn.com/helm/stable/debian/ all main" | sudo tee /etc/apt/sources.list.d/helm-stable-debian.list
sudo apt-get update && sudo apt-get install helm

Install on macOS
brew install helm

text

5. **kubelogin** - For Azure Kubernetes Service authentication
Install on Ubuntu/Debian
sudo az aks install-cli

Install on macOS
brew install Azure/kubelogin/kubelogin

text

## Azure Login

Before deploying, log in to your Azure account:

az login

text

## Deployment

The project includes a deployment script that automates the entire process:

1. **Run the deployment script**:
./deploy.sh

text

This script will:
- Initialize and apply Terraform to create Azure resources
- Build and push the Docker image to Azure Container Registry
- Deploy Dagster to AKS using Helm

2. **Verify deployment**:
kubectl get pods -n dagster

text

All pods should show `Running` status after a few minutes.

3. **Access the Dagster UI**:
kubectl port-forward svc/dagster-dagster-webserver 8080:80 -n dagster

text

Then open http://localhost:8080 in your browser.

## Input Data Setup

Upload your input data to Azure Blob Storage:

1. **Create a sample bounding box**:
[10.0, 45.0, 11.0, 46.0]

text
Save this as `bbox.json`

2. **Create sample field polygons**:
Use [geojson.io](https://geojson.io) to draw field polygons, then save as `fields.geojson`

3. **Upload to Azure Blob Storage**:
az storage blob upload-batch -s ./inputs/ -d inputs --account-name $(terraform -chdir=terraform output -raw storage_account_name)

text

## Running the Pipeline

1. Open the Dagster UI at http://localhost:8080
2. Navigate to the Assets tab
3. Select a date partition for the `hydrosat_data` asset
4. Click "Materialize" to process data for that date
5. View logs and results in the Runs tab

## Troubleshooting

If you encounter issues:

1. **Check pod logs**:
kubectl logs -n dagster <pod-name>

text

2. **Verify Azure connection string**:
Update the connection string in `helm/dagster-values.yaml` with your actual storage account key

3. **Restart a deployment**:
helm upgrade dagster dagster/dagster --namespace dagster -f helm/dagster-values.yaml

text

4. **Clean up and start over**:
helm uninstall dagster -n dagster
kubectl delete namespace dagster
./deploy.sh

