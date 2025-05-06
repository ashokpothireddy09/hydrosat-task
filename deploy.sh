#!/usr/bin/env bash
# One‑click: build image, deploy infrastructure (Terraform), push & install Dagster

set -euo pipefail

RG="${1:-hydro-rg}"
LOC="${2:-westeurope}"
PREFIX="${3:-hydro}"

echo "⏳ 1/4 Terraform apply ..."
cd terraform

terraform init -upgrade
terraform apply -auto-approve \
   -var="prefix=$PREFIX" \
   -var="location=$LOC" \
   -var='tags={"Environment"="Challenge","Owner"="you"}'


# ── read TF outputs ───────────────────────────────────────────────────────────
AKS_NAME=$(terraform output -raw aks_name)
ACR_NAME=$(terraform output -raw acr_name)
STORAGE_ACCOUNT=$(terraform output -raw storage_account_name)
RESOURCE_GROUP=$(terraform output -raw resource_group_name)
cd ..

# ── build connection‑string + key ─────────────────────────────────────────────
echo "⏳ 2/4 Fetching Storage credentials ..."
STORAGE_KEY=$(az storage account keys list                        \
                  --resource-group "$RESOURCE_GROUP"              \
                  --account-name   "$STORAGE_ACCOUNT"             \
                  --query "[0].value" -o tsv)

CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=${STORAGE_ACCOUNT};AccountKey=${STORAGE_KEY};EndpointSuffix=core.windows.net"

# ── patch Helm values file in‑place ───────────────────────────────────────────
VALUES_FILE="helm/dagster-values.yaml"
echo "   ↪ baking credentials into ${VALUES_FILE}"
# replace the *first* occurrence of AZURE_STORAGE_CONNECTION_STRING / _KEY
sed -i -e "/name: AZURE_STORAGE_CONNECTION_STRING/{n;s|value: .*|value: \"${CONNECTION_STRING}\"|}" \
       -e "/name: AZURE_STORAGE_KEY/{n;s|value: .*|value: \"${STORAGE_KEY}\"|}"                      \
       "${VALUES_FILE}"

# ──  get AKS credentials  ─────────────────────────────────────────────────────
echo "⏳ 3/4 Getting AKS kubeconfig ..."
az aks get-credentials -g "$RG" -n "$AKS_NAME" --admin --overwrite-existing

# make sure kubelogin is installed (OIDC -> azurecli)
if ! command -v kubelogin &>/dev/null; then
  echo "🔧 Installing kubelogin ..."
  tmp=$(mktemp -d)
  curl -sSL https://api.github.com/repos/Azure/kubelogin/releases/latest \
      | grep browser_download_url \
      | grep linux-amd64.zip \
      | cut -d '"' -f 4 \
      | xargs curl -L -o "${tmp}/kubelogin.zip"
  unzip -qo "${tmp}/kubelogin.zip" -d "${tmp}"
  install -m 755 "${tmp}"/bin/linux_amd64/kubelogin "$HOME/.local/bin/"
fi
kubelogin convert-kubeconfig -l azurecli

# ── build & push user‑code image ──────────────────────────────────────────────
echo "⏳ 4/4 Building Docker image and pushing to ACR ..."
az acr build \
   --registry "$ACR_NAME" \
   --image    hydrosat:latest \
   ./dagster

# ── helm install / upgrade ────────────────────────────────────────────────────
echo "⏳ Helm upgrade/install Dagster ..."
helm repo add dagster https://dagster-io.github.io/helm >/dev/null
helm repo update >/dev/null

helm upgrade --install dagster dagster/dagster \
  --namespace dagster --create-namespace \
  -f helm/dagster-values.yaml \
  --set dagster-user-deployments.deployments[0].image.repository="${ACR_NAME}.azurecr.io/hydrosat" \
  --set dagster-user-deployments.deployments[0].image.tag="latest"

echo "✅ Deployment finished!"
echo "↪  UI:  kubectl -n dagster port-forward svc/dagster-dagster-webserver 8080:80"
echo "↪  then open http://localhost:8080"


