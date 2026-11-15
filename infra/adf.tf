resource "azurerm_data_factory_linked_service_data_lake_storage_gen2" "lake" {
  name                 = "LakeManagedIdentity"
  data_factory_id      = azurerm_data_factory.main.id
  url                  = "https://${azurerm_storage_account.lake.name}.dfs.core.windows.net"
  use_managed_identity = true
}
resource "azurerm_data_factory_linked_custom_service" "ine" {
  name                 = "InePublicApi"
  data_factory_id      = azurerm_data_factory.main.id
  type                 = "RestService"
  type_properties_json = jsonencode({ url = "https://servicios.ine.es/wstempus/js/es/", enableServerCertificateValidation = true, authenticationType = "Anonymous" })
}
resource "azurerm_data_factory_linked_custom_service" "databricks" {
  name                 = "DatabricksManagedIdentity"
  data_factory_id      = azurerm_data_factory.main.id
  type                 = "AzureDatabricks"
  type_properties_json = jsonencode({ domain = "https://${azurerm_databricks_workspace.main.workspace_url}", authentication = "MSI", workspaceResourceId = azurerm_databricks_workspace.main.id, newClusterVersion = "17.3.x-scala2.13", newClusterNodeType = "Standard_D4ds_v5", newClusterNumOfWorker = "1", newClusterDataSecurityMode = "USER_ISOLATION" })
}
resource "azurerm_data_factory_custom_dataset" "datasets" {
  for_each        = { metadata = "metadata.json", source = "source.json", sink = "sink.json" }
  name            = jsondecode(file("${path.module}/../adf/datasets/${each.value}")).name
  data_factory_id = azurerm_data_factory.main.id
  type            = jsondecode(file("${path.module}/../adf/datasets/${each.value}")).properties.type
  linked_service { name = each.key == "source" ? azurerm_data_factory_linked_custom_service.ine.name : azurerm_data_factory_linked_service_data_lake_storage_gen2.lake.name }
  parameters           = each.key == "metadata" ? {} : { table_id = "", months = "60" }
  type_properties_json = jsonencode(jsondecode(file("${path.module}/../adf/datasets/${each.value}")).properties.typeProperties)
}
resource "databricks_workspace_file" "library" {
  for_each = fileset("${path.module}/../tourism", "*.py")
  path     = "/Shared/turismo/lib/tourism/${each.value}"
  source   = "${path.module}/../tourism/${each.value}"
}
resource "databricks_notebook" "pipeline" {
  path   = "/Shared/turismo/medallion"
  source = "${path.module}/../databricks/notebooks/medallion.ipynb"
}
resource "azurerm_data_factory_pipeline" "ingest" {
  name            = "TurismoMetadataIngest"
  data_factory_id = azurerm_data_factory.main.id
  activities_json = jsonencode(jsondecode(file("${path.module}/../adf/pipeline.json")).properties.activities)
  depends_on      = [azurerm_data_factory_custom_dataset.datasets, azurerm_data_factory_linked_custom_service.databricks, databricks_notebook.pipeline, databricks_workspace_file.library]
}
resource "azurerm_data_factory_trigger_schedule" "monthly" {
  name            = "MonthlyIngest"
  data_factory_id = azurerm_data_factory.main.id
  pipeline_name   = azurerm_data_factory_pipeline.ingest.name
  frequency       = "Month"
  interval        = 1
  start_time      = "2026-12-05T04:00:00Z"
  activated       = var.enable_monthly_trigger
  schedule {
    days_of_month = [5]
    hours         = [4]
    minutes       = [0]
  }
}
