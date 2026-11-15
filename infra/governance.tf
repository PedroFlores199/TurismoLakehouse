resource "databricks_metastore" "main" {
  count        = var.existing_metastore_id == null ? 1 : 0
  name         = "${local.name}-metastore"
  region       = var.location
  storage_root = "${local.lake_url}/metastore"
}
resource "databricks_metastore_assignment" "main" {
  metastore_id = local.metastore_id
  workspace_id = azurerm_databricks_workspace.main.workspace_id
}
resource "databricks_metastore_data_access" "main" {
  metastore_id = local.metastore_id
  name         = "lake-managed-identity"
  is_default   = true
  azure_managed_identity {
    access_connector_id = azurerm_databricks_access_connector.lake.id
  }
  depends_on = [azurerm_role_assignment.databricks_lake]
}
resource "databricks_storage_credential" "lake" {
  name = "turismo-lake"
  azure_managed_identity { access_connector_id = azurerm_databricks_access_connector.lake.id }
  depends_on = [databricks_metastore_assignment.main, azurerm_role_assignment.databricks_lake]
}
resource "databricks_external_location" "landing" {
  name            = "turismo-landing"
  url             = "${local.lake_url}/landing"
  credential_name = databricks_storage_credential.lake.name
}
resource "databricks_external_location" "managed" {
  name            = "turismo-managed"
  url             = "${local.lake_url}/catalog"
  credential_name = databricks_storage_credential.lake.name
}
resource "databricks_catalog" "tourism" {
  name         = "turismo"
  storage_root = "${local.lake_url}/catalog"
  depends_on   = [databricks_metastore_assignment.main, databricks_metastore_data_access.main, databricks_external_location.managed]
}
resource "databricks_schema" "layers" {
  for_each     = toset(["bronze", "silver", "gold"])
  name         = each.key
  catalog_name = databricks_catalog.tourism.name
}
resource "databricks_volume" "landing" {
  name             = "landing"
  catalog_name     = databricks_catalog.tourism.name
  schema_name      = databricks_schema.layers["bronze"].name
  volume_type      = "EXTERNAL"
  storage_location = databricks_external_location.landing.url
}



data "azuread_service_principal" "adf" {
  object_id = azurerm_data_factory.main.identity[0].principal_id
}
resource "databricks_service_principal" "adf" {
  application_id   = data.azuread_service_principal.adf.client_id
  display_name     = "Turismo Data Factory"
  workspace_access = true
}
resource "databricks_grants" "adf_catalog" {
  catalog = databricks_catalog.tourism.name
  grant {
    principal  = var.engineers_group
    privileges = ["USE_CATALOG"]
  }
  grant {
    principal  = var.readers_group
    privileges = ["USE_CATALOG"]
  }
  grant {
    principal  = databricks_service_principal.adf.application_id
    privileges = ["USE_CATALOG", "CREATE_SCHEMA"]
  }
}
resource "databricks_grants" "adf_layers" {
  for_each = toset(["bronze", "silver", "gold"])
  schema   = databricks_schema.layers[each.key].id
  grant {
    principal  = databricks_service_principal.adf.application_id
    privileges = ["ALL_PRIVILEGES"]
  }
  grant {
    principal  = var.engineers_group
    privileges = ["ALL_PRIVILEGES"]
  }
  dynamic "grant" {
    for_each = each.key == "gold" ? [var.readers_group] : []
    content {
      principal  = grant.value
      privileges = ["USE_SCHEMA", "SELECT"]
    }
  }
}
resource "databricks_grants" "landing" {
  volume = databricks_volume.landing.id
  grant {
    principal  = databricks_service_principal.adf.application_id
    privileges = ["READ_VOLUME", "WRITE_VOLUME"]
  }
}
