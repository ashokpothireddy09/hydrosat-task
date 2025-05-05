output "storage_account_blob_endpoint" {
  value = azurerm_storage_account.sa.primary_blob_endpoint
}

output "aks_name" {
  value = "${var.prefix}-aks"
}

output "resource_group_name" {
  value = azurerm_resource_group.rg.name
}

output "acr_name" {
  value = azurerm_container_registry.acr.name
}

output "storage_account_name" {
  value = azurerm_storage_account.sa.name
} 