data "azurerm_client_config" "current" {}
resource "random_id" "suffix" { byte_length = 3 }
locals {
  name         = "${var.prefix}${random_id.suffix.hex}"
  lake_url     = "abfss://lake@${azurerm_storage_account.lake.name}.dfs.core.windows.net"
  metastore_id = var.existing_metastore_id != null ? var.existing_metastore_id : databricks_metastore.main[0].id
  tags         = { project = "TurismoLakehouse", environment = "portfolio", owner = "PedroFlores199" }
}
resource "azurerm_resource_group" "main" {
  name     = "rg-${local.name}"
  location = var.location
  tags     = local.tags
}
resource "azurerm_storage_account" "lake" {
  name                            = local.name
  resource_group_name             = azurerm_resource_group.main.name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  is_hns_enabled                  = true
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  allow_nested_items_to_be_public = false
  min_tls_version                 = "TLS1_2"
  tags                            = local.tags
}
resource "azurerm_role_assignment" "bootstrap" {
  scope                = azurerm_storage_account.lake.id
  role_definition_name = "Storage Blob Data Owner"
  principal_id         = data.azurerm_client_config.current.object_id
}
resource "azurerm_storage_data_lake_gen2_filesystem" "lake" {
  name               = "lake"
  storage_account_id = azurerm_storage_account.lake.id
  depends_on         = [azurerm_role_assignment.bootstrap]
}
resource "azurerm_databricks_workspace" "main" {
  name                        = "dbw-${local.name}"
  resource_group_name         = azurerm_resource_group.main.name
  location                    = var.location
  sku                         = "premium"
  managed_resource_group_name = "rg-${local.name}-managed"
  tags                        = local.tags
}
resource "azurerm_databricks_access_connector" "lake" {
  name                = "dbc-${local.name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  identity { type = "SystemAssigned" }
  tags = local.tags
}
resource "azurerm_role_assignment" "databricks_lake" {
  scope                = azurerm_storage_account.lake.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_databricks_access_connector.lake.identity[0].principal_id
}
resource "azurerm_data_factory" "main" {
  name                = "adf-${local.name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  identity { type = "SystemAssigned" }
  tags = local.tags
}
resource "azurerm_role_assignment" "adf_lake" {
  scope                = azurerm_storage_account.lake.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_data_factory.main.identity[0].principal_id
}
resource "azurerm_role_assignment" "adf_workspace" {
  scope                = azurerm_databricks_workspace.main.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_data_factory.main.identity[0].principal_id
}
resource "azurerm_key_vault" "main" {
  name                       = "kv-${local.name}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = var.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 7
  tags                       = local.tags
}
resource "azurerm_role_assignment" "adf_vault" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_data_factory.main.identity[0].principal_id
}
resource "azurerm_storage_blob" "metadata" {
  name                   = "metadata/sources.json"
  storage_account_name   = azurerm_storage_account.lake.name
  storage_container_name = azurerm_storage_data_lake_gen2_filesystem.lake.name
  type                   = "Block"
  source                 = "${path.module}/../adf/sources.json"
  content_type           = "application/json"
}
