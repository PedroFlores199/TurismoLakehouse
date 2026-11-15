terraform {
  required_version = ">= 1.9, < 2"
  required_providers {
    azurerm    = { source = "hashicorp/azurerm", version = "~> 4.0" }
    azuread    = { source = "hashicorp/azuread", version = "~> 3.0" }
    databricks = { source = "databricks/databricks", version = "~> 1.0" }
    random     = { source = "hashicorp/random", version = "~> 3.6" }
  }
}
provider "azurerm" {
  features {}
  subscription_id     = var.subscription_id
  storage_use_azuread = true
}
provider "azuread" {}
provider "databricks" {
  host                        = "https://${azurerm_databricks_workspace.main.workspace_url}"
  azure_workspace_resource_id = azurerm_databricks_workspace.main.id
}
