############################
# 1 ─ Resource Group
############################
resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-rg"
  location = var.location
  tags     = local.common_tags
}

############################
# 2 ─ VNet & Subnets
############################
module "vnet" {
  source  = "Azure/vnet/azurerm"
  version = "4.0.0"

  use_for_each        = true
  resource_group_name = azurerm_resource_group.rg.name
  vnet_name           = "${var.prefix}-vnet"
  vnet_location       = var.location
  address_space       = ["10.0.0.0/16"]

  subnet_prefixes = [
    "10.0.0.0/22",  # aks_system
    "10.0.4.0/22",  # aks_user
    "10.0.8.0/24"   # private_endpoints
  ]

  subnet_names = [
    "aks_system",
    "aks_user",
    "private_endpoints"
  ]

  subnet_service_endpoints = {
    aks_system        = ["Microsoft.Storage"]
    aks_user          = ["Microsoft.Storage"]
    private_endpoints = []
  }
}

############################
# 3 ─ Storage Account
############################
resource "random_id" "rand" { byte_length = 3 }

resource "azurerm_storage_account" "sa" {
  name                      = lower("${var.prefix}${random_id.rand.hex}sa")
  resource_group_name       = azurerm_resource_group.rg.name
  location                  = var.location
  account_tier              = "Standard"
  account_replication_type  = "ZRS"
  https_traffic_only_enabled = true  # Updated from enable_https_traffic_only
  min_tls_version           = "TLS1_2"
  network_rules {
    default_action             = "Deny"
    bypass                     = ["AzureServices"]
    virtual_network_subnet_ids = [module.vnet.vnet_subnets_name_id["aks_system"]]
  }
  tags = local.common_tags
}

resource "azurerm_storage_container" "inputs" {
  name                  = "inputs"
  storage_account_name  = azurerm_storage_account.sa.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "outputs" {
  name                  = "outputs"
  storage_account_name  = azurerm_storage_account.sa.name
  container_access_type = "private"
}

resource "azurerm_private_endpoint" "sa_pe" {
  name                = "${var.prefix}-sa-pe"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = module.vnet.vnet_subnets_name_id["private_endpoints"]

  private_service_connection {
    name                           = "${var.prefix}-sa-conn"
    private_connection_resource_id = azurerm_storage_account.sa.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }
  tags = local.common_tags
}

############################
# 4 ─ Container Registry
############################
resource "azurerm_container_registry" "acr" {
  name                = lower("${var.prefix}${random_id.rand.hex}acr")
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
  sku                 = "Premium"
  admin_enabled       = false
  tags                = local.common_tags
}

############################
# 5 ─ AKS Cluster
############################
module "aks" {
  source  = "Azure/aks/azurerm"
  version = "7.5.0"

  prefix                   = var.prefix
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = var.location
  kubernetes_version       = var.kubernetes_version

  # networking
  private_cluster_enabled  = true
  vnet_subnet_id           = module.vnet.vnet_subnets_name_id["aks_system"]
  network_plugin           = "azure"
  network_policy           = "calico"

  # identity
  rbac_aad_managed         = true

  node_pools = {
    system = {
      name                = "system"
      vm_size             = "Standard_D4ads_v5"
      node_count          = 1
      enable_auto_scaling = true
      min_count           = 1
      max_count           = 3
    }
  }

  tags = local.common_tags
}

############################
# 6 ─ IAM bindings
############################
resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = module.aks.kubelet_identity[0].object_id
}

resource "azurerm_role_assignment" "aks_sa_blob" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = module.aks.kubelet_identity[0].object_id
}
