#!/usr/bin/env bash
set -euo pipefail

RG=${1:-hydro-rg}
LOC=${2:-westeurope}
PREFIX=${3:-hydro}

echo "⏳ 1/4 Terraform apply ..."
cd terraform
terraform init -upgrade
terraform apply -auto-approve \
   -var="prefix=$PREFIX" -var="location=$LOC" -var="tags={Owner=you,Environment=Challenge}"
AKS_NAME=$(terraform output -raw aks_name)
ACR_NAME=$(terraform output -raw acr_name)
STORAGE=$(terraform output -raw storage_account_name)
cd ..

echo "⏳ 2/4 Get AKS creds ..."
az aks get-credentials -g "$RG" -n "$AKS_NAME" --overwrite-existing

echo "⏳ 3/4 Build & push image ..."
az acr login -n "$ACR_NAME"
docker build -t "$ACR_NAME.azurecr.io/hydrosat:latest" ./dagster
docker push "$ACR_NAME.azurecr.io/hydrosat:latest"

echo "⏳ 4/4 Helm install Dagster ..."
helm repo add dagster https://dagster-io.github.io/helm
helm repo update
helm upgrade --install dagster dagster/dagster \
   --namespace dagster --create-namespace \
   -f helm/dagster-values.yaml \
   --set userCodeDeployments[0].image.repository="$ACR_NAME.azurecr.io/hydrosat"

echo "✅ Done. Run  ➜  kubectl -n dagster get svc dagster-dagster-webserver" 