#!/usr/bin/env bash
set -euo pipefail

RG=${1:-hydro-rg}
LOC=${2:-westeurope}
PREFIX=${3:-hydro}

echo "⏳ 1/4 Terraform apply ..."
cd terraform

AKS_NAME=$(terraform output -raw aks_name)
ACR_NAME=$(terraform output -raw acr_name)
STORAGE=$(terraform output -raw storage_account_name)
cd ..

echo "⏳ 2/4 Get AKS creds ..."
# Install kubelogin before getting credentials
if ! command -v kubelogin &> /dev/null; then
    echo "Installing kubelogin..."
    # Create local bin directory if it doesn't exist
    mkdir -p $HOME/.local/bin
    
    # For Linux - download kubelogin directly
    KUBELOGIN_VERSION=$(curl -s https://api.github.com/repos/Azure/kubelogin/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')
    curl -L https://github.com/Azure/kubelogin/releases/download/${KUBELOGIN_VERSION}/kubelogin-linux-amd64.zip -o kubelogin.zip
    unzip -o kubelogin.zip
    mv bin/linux_amd64/kubelogin $HOME/.local/bin/
    chmod +x $HOME/.local/bin/kubelogin
    rm -rf bin/ kubelogin.zip
    
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        export PATH="$PATH:$HOME/.local/bin"
        echo 'export PATH="$PATH:$HOME/.local/bin"' >> $HOME/.bashrc
    fi
    
    # Install kubectl if needed
    if ! command -v kubectl &> /dev/null; then
        echo "Installing kubectl..."
        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
        chmod +x kubectl
        mv kubectl $HOME/.local/bin/
    fi
fi

# Get AKS credentials with admin access for simplicity

az aks get-credentials -g "$RG" -n "$AKS_NAME" --admin --overwrite-existing

# For production, consider setting up proper RBAC instead of using --admin
# See: https://docs.microsoft.com/en-us/azure/aks/manage-azure-rbac
#echo "Applying RBAC configuration..."
#USER_NAME=$(az account show --query user.name -o tsv)
#sed "s/\$(az account show --query user.name -o tsv)/$USER_NAME/g" k8s/rbac/dagster-rbac.yaml | kubectl apply -f -

# Convert kubeconfig to use azurecli login method
$HOME/.local/bin/kubelogin convert-kubeconfig -l azurecli

echo "⏳ 3/4 Build & push image ..."
az acr build \
   --registry "$ACR_NAME" \
   --image hydrosat:latest \
   ./dagster

echo "⏳ 4/4 Helm install Dagster ..."
helm repo add dagster https://dagster-io.github.io/helm
helm repo update
helm upgrade --install dagster dagster/dagster \
   --namespace dagster --create-namespace \
   -f helm/dagster-values.yaml \
   --set dagster-user-deployments.deployments[0].image.repository="$ACR_NAME.azurecr.io/hydrosat" \
   --set dagster-user-deployments.deployments[0].image.tag="latest"

echo "✅ Done. Run  ➜  kubectl -n dagster get svc dagster-dagster-webserver"

echo "Checking Dagster pod status..."
kubectl get pods -n dagster

echo "To access Dagster UI, run:"
echo "kubectl -n dagster port-forward svc/dagster-dagster-webserver 8080:80"
echo "Then visit http://127.0.0.1:8080 in your browser"



terraform init -upgrade
terraform apply -auto-approve \
   -var="prefix=$PREFIX" \
   -var="location=$LOC" \
   -var='tags={"Environment"="Challenge","Owner"="you"}'