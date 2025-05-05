resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-rg"
  location = var.location
  tags     = var.tags
}

# ----------------------- NETWORK -----------------------
module "vnet" {
  source  = "Azure/vnet/azurerm"
  version = "4.2.0"

  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
  vnet_name           = "${var.prefix}-vnet"
  address_space       = ["10.0.0.0/16"]

  subnet_prefixes = {
    aks_system         = "10.0.0.0/22"
    aks_user           = "10.0.4.0/22"
    private_endpoints  = "10.0.8.0/24"
  }
  subnet_names = keys(subnet_prefixes)
  subnet_service_endpoints = {
    aks_system        = ["Microsoft.Storage"]
    aks_user          = ["Microsoft.Storage"]
    private_endpoints = []
  }
  tags = var.tags
}

# ----------------------- STORAGE -----------------------
resource "random_id" "rand" { byte_length = 3 }

resource "azurerm_storage_account" "sa" {
  name                     = lower("${var.prefix}${random_id.rand.hex}sa")
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "ZRS"
  enable_https_traffic_only = true
  min_tls_version          = "TLS1_2"
  network_rules { 
    default_action = "Deny" 
    bypass = ["AzureServices"] 
    virtual_network_subnet_ids = [module.vnet.subnets["aks_system"].id] 
  }
  tags = var.tags
}

resource "azurerm_storage_container" "inputs"  { name = "inputs";  storage_account_name = azurerm_storage_account.sa.name  }
resource "azurerm_storage_container" "outputs" { name = "outputs"; storage_account_name = azurerm_storage_account.sa.name  }

resource "azurerm_private_endpoint" "sa_pe" {
  name                = "${var.prefix}-sa-pe"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = module.vnet.subnets["private_endpoints"].id
  private_service_connection {
    name                           = "blob"
    subresource_names              = ["blob"]
    private_connection_resource_id = azurerm_storage_account.sa.id
    is_manual_connection           = false
  }
  tags = var.tags
}

# ----------------------- CONTAINER REGISTRY -----------------------
resource "azurerm_container_registry" "acr" {
  name                = lower("${var.prefix}${random_id.rand.hex}acr")
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
  sku                 = "Premium"
  admin_enabled       = false
  tags                = var.tags
}

# ----------------------- AKS -----------------------
module "aks" {
  source  = "Azure/aks/azurerm"
  version = "7.5.0"

  prefix                    = var.prefix
  resource_group_name       = azurerm_resource_group.rg.name
  kubernetes_version        = var.kubernetes_version
  location                  = var.location
  network_plugin            = "azure"
  private_cluster_enabled   = true
  enable_workload_identity  = true
  rbac_aad_managed          = true
  network_policy            = "calico"
  vnet_subnet_id            = module.vnet.subnets["aks_system"].id
  node_pools = {
    system = { vm_size = "Standard_D4ads_v5", node_count = 1, min_count = 1, max_count = 3 }
  }
  tags = var.tags
}

# Allow AKS to pull from ACR
resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = module.aks.kubelet_identity_oid
}

# Storage access for managed identity
resource "azurerm_role_assignment" "aks_sa_blob" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = module.aks.user_assigned_identity_id
}

# ----------------------- OUTPUTS -----------------------
output "rg_name"              { value = azurerm_resource_group.rg.name }
output "aks_name"             { value = module.aks.aks_name }
output "acr_name"             { value = azurerm_container_registry.acr.name }
output "storage_account_name" { value = azurerm_storage_account.sa.name } 