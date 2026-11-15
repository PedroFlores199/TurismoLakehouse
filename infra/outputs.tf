output "resource_group" { value = azurerm_resource_group.main.name }
output "workspace_url" { value = "https://${azurerm_databricks_workspace.main.workspace_url}" }
output "data_factory" { value = azurerm_data_factory.main.name }
output "key_vault" { value = azurerm_key_vault.main.vault_uri }
output "lake" { value = local.lake_url }
output "cleanup" { value = "terraform destroy -var-file=local.tfvars" }
