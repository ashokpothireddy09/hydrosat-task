###############################################################################
# 0 ─  Who am I?  (caller's object‑ID used for Storage RBAC)
###############################################################################
data "azurerm_client_config" "current" {}

###############################################################################
# 1 ─  Resource Group
###############################################################################
resource "azurerm_resource_group" "rg" {
  name     = "hydro-rg"
  location = var.location
  tags     = local.common_tags
}

###############################################################################
# 2 ─  VNet and subnets
###############################################################################
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

  subnet_names = ["aks_system", "aks_user", "private_endpoints"]

  subnet_service_endpoints = {
    aks_system        = ["Microsoft.Storage"]
    aks_user          = ["Microsoft.Storage"]
    private_endpoints = []
  }
}

###############################################################################
# 3 ─  Storage Account(+ RBAC + PE + containers)
###############################################################################
resource "random_id" "rand" { byte_length = 3 }

resource "azurerm_storage_account" "sa" {
  name                       = lower("${var.prefix}${random_id.rand.hex}sa")
  resource_group_name        = azurerm_resource_group.rg.name
  location                   = var.location
  account_tier               = "Standard"
  account_replication_type   = "ZRS"
  https_traffic_only_enabled = true
  min_tls_version            = "TLS1_2"

  # ⚠ keep open during apply; lock down later
  network_rules {
    default_action = "Allow"
    bypass         = ["AzureServices"]
  }

  tags = local.common_tags
}

# management‑plane → data‑plane RBAC
resource "azurerm_role_assignment" "tf_sa_blob" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}

# wait up to 45 s for ACL propagation
resource "time_sleep" "wait_for_rbac" {
  depends_on      = [azurerm_role_assignment.tf_sa_blob]
  create_duration = "45s"
}

# private endpoint
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

resource "azurerm_storage_container" "inputs" {
  name                  = "inputs"
  storage_account_name  = azurerm_storage_account.sa.name
  container_access_type = "private"
  depends_on            = [time_sleep.wait_for_rbac]
}

resource "azurerm_storage_container" "outputs" {
  name                  = "outputs"
  storage_account_name  = azurerm_storage_account.sa.name
  container_access_type = "private"
  depends_on            = [time_sleep.wait_for_rbac]
}

###############################################################################
# 4 ─  Premium ACR
###############################################################################
resource "azurerm_container_registry" "acr" {
  name                = lower("${var.prefix}${random_id.rand.hex}acr")
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
  sku                 = "Premium"
  admin_enabled       = false
  tags                = local.common_tags
}

###############################################################################
# 5 ─  AKS 1.30 LTS (no Calico)
###############################################################################
module "aks" {
  source  = "Azure/aks/azurerm"
  version = "9.0.0"

  prefix              = var.prefix
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location

  kubernetes_version  = "1.30.3"
  sku_tier            = "Premium"
  support_plan        = "AKSLongTermSupport"

  private_cluster_enabled = false
  vnet_subnet_id          = module.vnet.vnet_subnets_name_id["aks_system"]
  network_plugin          = "azure"
  network_plugin_mode     = "overlay"
  # Calico not supported on LTS overlay

  net_profile_pod_cidr       = "192.168.0.0/16"
  net_profile_service_cidr   = "172.17.0.0/16"
  net_profile_dns_service_ip = "172.17.0.10"

  rbac_aad_managed                  = true
  role_based_access_control_enabled = true

  node_pools = {
    system = {
      name                = "system"
      vm_size             = "Standard_D4s_v5"
      node_count          = 1
      enable_auto_scaling = true
      min_count           = 1
      max_count           = 3
    }
  }

  tags = local.common_tags
  depends_on = [azurerm_resource_group.rg]
}

###############################################################################
# 6 ─  Fetch kubelet identity
###############################################################################
data "azurerm_kubernetes_cluster" "aks" {
  name                = "${var.prefix}-aks"
  resource_group_name = azurerm_resource_group.rg.name
  depends_on          = [module.aks]
}

###############################################################################
# 7 ─  Role assignments for kubelet identity
###############################################################################
resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = data.azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
}

resource "azurerm_role_assignment" "aks_sa_blob" {
  scope                = azurerm_storage_account.sa.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = data.azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
}
