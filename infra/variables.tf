variable "subscription_id" { type = string }
variable "prefix" {
  type    = string
  default = "pfturismo"
  validation {
    condition     = can(regex("^[a-z][a-z0-9]{3,11}$", var.prefix))
    error_message = "Usa entre 4 y 12 letras minúsculas o números."
  }
}
variable "location" {
  type    = string
  default = "westeurope"
}
variable "engineers_group" { type = string }
variable "readers_group" { type = string }
variable "existing_metastore_id" {
  type    = string
  default = null
}
variable "allow_billable_resources" {
  type    = bool
  default = false
  validation {
    condition     = var.allow_billable_resources
    error_message = "Revisa docs/costs.md y autoriza los recursos antes de establecer allow_billable_resources=true."
  }
}
variable "enable_monthly_trigger" {
  type    = bool
  default = false
}
