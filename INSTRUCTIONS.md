# 📋 Setup and Deployment Instructions

This document provides comprehensive instructions for setting up and deploying the Hydrosat geospatial pipeline on Azure.

## 🔧 Prerequisites

Before beginning deployment, ensure you have the following tools installed on your development machine:

### Azure CLI

The Azure Command-Line Interface is required for interacting with Azure services.

<details>
<summary>Installation Instructions</summary>

**Ubuntu/Debian:**
```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

**macOS:**
```bash
brew install azure-cli
```

**Windows:**
```powershell
winget install -e --id Microsoft.AzureCLI
```

**Verify installation:**
```bash
az --version
```
</details>

### Terraform

Terraform is used for Infrastructure as Code (IaC) to provision and manage Azure resources.

<details>
<summary>Installation Instructions</summary>

**Ubuntu/Debian:**
```bash
sudo apt-get update && sudo apt-get install -y gnupg software-properties-common
wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt-get update && sudo apt-get install terraform
```

**macOS:**
```bash
brew install terraform
```

**Windows:**
```powershell
winget install -e --id Hashicorp.Terraform
```

**Verify installation:**
```bash
terraform --version
```
</details>

### kubectl

The Kubernetes command-line tool for controlling Kubernetes clusters.

<details>
<summary>Installation Instructions</summary>

**Ubuntu/Debian:**
```bash
sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates curl
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.28/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.28/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update && sudo apt-get install -y kubectl
```

**macOS:**
```bash
brew install kubectl
```

**Windows:**
```powershell
winget install -e --id Kubernetes.kubectl
```

**Verify installation:**
```bash
kubectl version --client
```
</details>

### Helm

Helm is the package manager for Kubernetes, used to deploy Dagster.

<details>
<summary>Installation Instructions</summary>

**Ubuntu/Debian:**
```bash
curl https://baltocdn.com/helm/signing.asc | sudo apt-key add -
sudo apt-get install apt-transport-https --yes
echo "deb https://baltocdn.com/helm/stable/debian/ all main" | sudo tee /etc/apt/sources.list.d/helm-stable-debian.list
sudo apt-get update && sudo apt-get install helm
```

**macOS:**
```bash
brew install helm
```

**Windows:**
```powershell
winget install -e --id Helm.Helm
```

**Verify installation:**
```bash
helm version
```
</details>

### kubelogin (for Azure AKS authentication)

Kubelogin is a helper tool for authenticating with Azure Kubernetes Service.

<details>
<summary>Installation Instructions</summary>

**Ubuntu/Debian:**
```bash
sudo az aks install-cli
```

**macOS:**
```bash
brew install Azure/kubelogin/kubelogin
```

**Windows:**
```powershell
az aks install-cli
```

**Verify installation:**
```bash
kubelogin --version
```
</details>

## 🔐 Azure Account Setup

### Login to Azure

```bash
az login
```

If you're using a specific subscription:

```bash
az account set --subscription "<subscription-id>"
```

### Service Principal (Optional for CI/CD)

For automated CI/CD deployment, create a service principal:

```bash
az ad sp create-for-rbac --name "hydrosat-pipeline" --role Contributor --scopes /subscriptions/<subscription-id>
```

Save the output credentials securely for use in CI/CD systems.

## 🚀 Deployment

The project includes a comprehensive deployment script that automates the entire process:

### One-Click Deployment

```bash
./deploy.sh
```

This script performs the following steps:

1. Initializes Terraform and creates Azure infrastructure
2. Builds the Docker image and pushes it to Azure Container Registry
3. Authenticates with AKS and applies Kubernetes configurations
4. Deploys Dagster using Helm with custom values
5. Sets up storage containers and prepares the environment

### Custom Deployment Options

The deploy script accepts optional parameters:

```bash
./deploy.sh <resource-group-name> <location> <prefix>
```

- `<resource-group-name>`: Azure resource group name (default: `hydro-rg`)
- `<location>`: Azure region (default: `westeurope`)
- `<prefix>`: Resource name prefix (default: `hydro`)

Example with custom values:
```bash
./deploy.sh hydrosat-prod-rg eastus hydrosat-prod
```

### Manual Deployment Steps

If you prefer step-by-step deployment or need to troubleshoot:

<details>
<summary>Expand for manual deployment steps</summary>

#### 1. Terraform Infrastructure

```bash
cd terraform
terraform init
terraform apply -var="prefix=hydrosat" -var="location=westeurope"
```

Save the outputs for the next steps:
```bash
AKS_NAME=$(terraform output -raw aks_name)
ACR_NAME=$(terraform output -raw acr_name)
STORAGE_ACCOUNT=$(terraform output -raw storage_account_name)
RESOURCE_GROUP=$(terraform output -raw resource_group_name)
```

#### 2. Configure Storage

Get the storage account key:
```bash
STORAGE_KEY=$(az storage account keys list \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$STORAGE_ACCOUNT" \
    --query "[0].value" -o tsv)
```

Create connection string:
```bash
CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=${STORAGE_ACCOUNT};AccountKey=${STORAGE_KEY};EndpointSuffix=core.windows.net"
```

Update Helm values:
```bash
sed -i -e "/name: AZURE_STORAGE_CONNECTION_STRING/{n;s|value: .*|value: \"${CONNECTION_STRING}\"|}" \
       -e "/name: AZURE_STORAGE_KEY/{n;s|value: .*|value: \"${STORAGE_KEY}\"|}" \
       "helm/dagster-values.yaml"
```

#### 3. Connect to AKS

```bash
az aks get-credentials -g "$RESOURCE_GROUP" -n "$AKS_NAME" --admin
kubelogin convert-kubeconfig -l azurecli
```

#### 4. Build and Push Docker Image

```bash
az acr build \
   --registry "$ACR_NAME" \
   --image hydrosat:latest \
   ./dagster
```

#### 5. Deploy Dagster with Helm

```bash
helm repo add dagster https://dagster-io.github.io/helm
helm repo update

helm upgrade --install dagster dagster/dagster \
  --namespace dagster --create-namespace \
  -f helm/dagster-values.yaml \
  --set dagster-user-deployments.deployments[0].image.repository="${ACR_NAME}.azurecr.io/hydrosat" \
  --set dagster-user-deployments.deployments[0].image.tag="latest"
```
</details>

### Verification

Verify that all pods are running:

```bash
kubectl get pods -n dagster
```

Expected output:
```
NAME                                                          READY   STATUS    RESTARTS   AGE
dagster-daemon-848f5bf5f5-vtnbb                               1/1     Running   0          5m
dagster-dagster-user-deployments-hydrosat-code-7bf94f45ff-xxxx 1/1     Running   0          5m
dagster-dagster-webserver-75c6474668-5tp5t                    1/1     Running   0          5m
dagster-postgresql-0                                          1/1     Running   0          5m
dagster-rabbitmq-0                                            1/1     Running   0          5m
```

## 🖥️ Accessing the Dagster UI

Forward the Dagster webserver port to your local machine:

```bash
kubectl port-forward svc/dagster-dagster-webserver 8080:80 -n dagster
```

Open your browser and navigate to: [http://localhost:8080](http://localhost:8080)

## 🌱 Running the Pipeline

### Materializing Assets

In the Dagster UI:

1. Go to the **Assets** tab
2. Select the **hydrosat_data** asset
3. Choose a date partition (e.g., "2025-05-04")
4. Click **Materialize Selection**
5. After completion, materialize the next day's data (e.g., "2025-05-05")
6. Finally, materialize the **dependent_asset** for the latest date

### Expected Outputs

After successful materialization, you should see:

1. In the **hydrosat_data** asset:
   - Raw data CSV/JSON files for each date
   - Raster visualization PNGs for NDVI, soil moisture, and temperature

2. In the **dependent_asset**:
   - Change analysis CSV files
   - Field summary visualizations showing day-over-day changes

### Verify in Azure Blob Storage

Check the outputs in Azure Blob Storage:

```bash
# List files in the outputs container
az storage blob list \
  --container-name outputs \
  --account-name $STORAGE_ACCOUNT \
  --output table
```

You should see files like:
- `hydrosat_data_2025-05-04.csv`
- `hydrosat_data_2025-05-05.csv`
- `hydrosat_changes_2025-05-05.csv`
- In the `plots` folder: field summaries and visualizations

## 🔍 Troubleshooting

### Common Issues and Solutions

<details>
<summary>Pod startup failures</summary>

**Symptom:** Pods remain in "Pending" or show "Error" status

**Check pod details:**
```bash
kubectl describe pod <pod-name> -n dagster
```

**Common causes and solutions:**
- **Image pull error**: Check ACR credentials and image name
  ```bash
  # Verify ACR credentials are properly configured
  kubectl create secret docker-registry acr-secret \
    --docker-server=${ACR_NAME}.azurecr.io \
    --docker-username=${ACR_NAME} \
    --docker-password=$(az acr credential show -n ${ACR_NAME} --query "passwords[0].value" -o tsv) \
    --namespace dagster
  ```

- **Resource constraints**: AKS cluster may need more resources
  ```bash
  # Scale up the node pool
  az aks nodepool scale --resource-group $RESOURCE_GROUP --cluster-name $AKS_NAME --name agentpool --node-count 3
  ```
</details>

<details>
<summary>Storage connection issues</summary>

**Symptom:** Assets fail with storage access errors

**Check environment variables:**
```bash
# Get the pod name
POD_NAME=$(kubectl get pods -n dagster -l app.kubernetes.io/component=user-code-deployment -o jsonpath="{.items[0].metadata.name}")

# Check environment variables
kubectl exec -n dagster $POD_NAME -- env | grep AZURE
```

**Verify storage account:**
```bash
# Test storage access
az storage container list --account-name $STORAGE_ACCOUNT --auth-mode login
```

**Solution:**
Update the connection string and key in the Helm values:
```bash
# Get latest key
STORAGE_KEY=$(az storage account keys list --resource-group "$RESOURCE_GROUP" --account-name "$STORAGE_ACCOUNT" --query "[0].value" -o tsv)

# Update Helm deployment
helm upgrade dagster dagster/dagster \
  --namespace dagster \
  -f helm/dagster-values.yaml \
  --set env[0].value="DefaultEndpointsProtocol=https;AccountName=${STORAGE_ACCOUNT};AccountKey=${STORAGE_KEY};EndpointSuffix=core.windows.net" \
  --set env[1].value="${STORAGE_KEY}"
```
</details>

<details>
<summary>Dagster UI connection issues</summary>

**Symptom:** Cannot access Dagster UI at localhost:8080

**Check webserver pod:**
```bash
kubectl get pods -n dagster -l app.kubernetes.io/component=dagster-webserver
```

**Check service:**
```bash
kubectl get svc -n dagster
```

**Solution:**
If the port-forward isn't working, try exposing the service:
```bash
# Option 1: Change service type to LoadBalancer
kubectl patch svc dagster-dagster-webserver -n dagster -p '{"spec": {"type": "LoadBalancer"}}'

# Option 2: Use a different local port
kubectl port-forward svc/dagster-dagster-webserver 8000:80 -n dagster
```
</details>

<details>
<summary>Asset materialization failures</summary>

**Symptom:** Assets fail during materialization

**Check logs:**
```bash
# Find the run ID from the Dagster UI or:
RUN_ID=$(kubectl exec -n dagster $POD_NAME -- dagster run list --limit 1 -o json | jq -r '.[0].id')

# View logs
kubectl exec -n dagster $POD_NAME -- dagster run logs $RUN_ID
```

**Common errors:**
- Missing Python dependencies: Update the Dockerfile
- Missing adlfs package: Add to Dockerfile
- Path errors: Check the paths in assets.py

**Redeploying after code changes:**
```bash
# Rebuild the image
az acr build --registry "$ACR_NAME" --image hydrosat:latest ./dagster

# Update the deployment
kubectl rollout restart deployment -n dagster -l app.kubernetes.io/component=user-code-deployment
```
</details>

## 🧹 Cleanup

To delete all resources when you're done:

```bash
# Delete Dagster deployment
helm uninstall dagster -n dagster

# Delete namespace
kubectl delete namespace dagster

# Delete Azure resources
cd terraform
terraform destroy -auto-approve
```

## 🔄 Updating the Pipeline

### Modifying Code

1. Edit files in `dagster/hydrosat_project/`
2. Rebuild and redeploy:
   ```bash
   # Build new image
   az acr build --registry "$ACR_NAME" --image hydrosat:latest ./dagster
   
   # Restart deployment
   kubectl rollout restart deployment -n dagster -l app.kubernetes.io/component=user-code-deployment
   ```

### Scaling the Pipeline

To handle larger workloads:

```bash
# Scale AKS nodes
az aks nodepool scale \
  --resource-group $RESOURCE_GROUP \
  --cluster-name $AKS_NAME \
  --name agentpool \
  --node-count 5

# Increase resources for Dagster pods (edit values.yaml first)
helm upgrade dagster dagster/dagster \
  --namespace dagster \
  -f helm/dagster-values.yaml
```

## 📊 Monitoring

### Kubernetes Dashboard

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/dashboard/v2.7.0/aio/deploy/recommended.yaml
kubectl proxy
```

Access at: [http://localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:/proxy/](http://localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:/proxy/)

### Azure Monitoring

```bash
# Enable monitoring
az aks enable-addons \
  --resource-group $RESOURCE_GROUP \
  --name $AKS_NAME \
  --addons monitoring
```

View metrics in the Azure Portal under your AKS cluster's "Insights" section.

---

## 🎯 Next Steps

After deploying the pipeline, consider:

1. **Automating with Schedules**: Configure Dagster schedules to run daily
2. **Adding Alerting**: Set up monitoring and alerting for failures
3. **Integrating with Data Consumers**: Connect outputs to downstream systems
4. **Enhancing Security**: Add Azure Private Endpoints and RBAC refinements

For any issues not covered in troubleshooting, please open an issue in the repository.