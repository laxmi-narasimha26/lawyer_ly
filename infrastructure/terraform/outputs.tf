# Outputs for Indian Legal AI Assistant Terraform configuration

output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "resource_group_location" {
  description = "Location of the resource group"
  value       = azurerm_resource_group.main.location
}

# Network outputs
output "virtual_network_id" {
  description = "ID of the virtual network"
  value       = module.network.virtual_network_id
}

output "virtual_network_name" {
  description = "Name of the virtual network"
  value       = module.network.virtual_network_name
}

output "container_apps_subnet_id" {
  description = "ID of the container apps subnet"
  value       = module.network.container_apps_subnet_id
}

# Container Apps outputs
output "frontend_url" {
  description = "URL of the frontend application"
  value       = module.container_apps.frontend_url
  sensitive   = false
}

output "backend_url" {
  description = "URL of the backend API"
  value       = module.container_apps.backend_url
  sensitive   = false
}

output "container_app_environment_id" {
  description = "ID of the Container App Environment"
  value       = module.container_apps.container_app_environment_id
}

# Database outputs
output "database_server_name" {
  description = "Name of the PostgreSQL server"
  value       = module.database.server_name
}

output "database_server_fqdn" {
  description = "FQDN of the PostgreSQL server"
  value       = module.database.server_fqdn
  sensitive   = true
}

output "database_name" {
  description = "Name of the database"
  value       = module.database.database_name
}

# Cache outputs
output "redis_cache_name" {
  description = "Name of the Redis cache"
  value       = module.cache.cache_name
}

output "redis_cache_hostname" {
  description = "Hostname of the Redis cache"
  value       = module.cache.hostname
  sensitive   = true
}

# Storage outputs
output "storage_account_name" {
  description = "Name of the storage account"
  value       = module.storage.storage_account_name
}

output "storage_account_primary_endpoint" {
  description = "Primary endpoint of the storage account"
  value       = module.storage.primary_blob_endpoint
}

output "storage_container_name" {
  description = "Name of the storage container"
  value       = module.storage.container_name
}

# Container Registry outputs
output "container_registry_name" {
  description = "Name of the container registry"
  value       = module.container_registry.registry_name
}

output "container_registry_login_server" {
  description = "Login server of the container registry"
  value       = module.container_registry.login_server
}

# Security outputs
output "key_vault_name" {
  description = "Name of the Key Vault"
  value       = module.security.key_vault_name
}

output "key_vault_uri" {
  description = "URI of the Key Vault"
  value       = module.security.key_vault_uri
  sensitive   = true
}

# Monitoring outputs
output "log_analytics_workspace_name" {
  description = "Name of the Log Analytics workspace"
  value       = module.monitoring.log_analytics_workspace_name
}

output "application_insights_name" {
  description = "Name of the Application Insights instance"
  value       = module.monitoring.application_insights_name
}

output "application_insights_instrumentation_key" {
  description = "Instrumentation key for Application Insights"
  value       = module.monitoring.application_insights_instrumentation_key
  sensitive   = true
}

# Connection information for applications
output "connection_info" {
  description = "Connection information for applications"
  value = {
    frontend_url = module.container_apps.frontend_url
    backend_url  = module.container_apps.backend_url
    
    # These are stored in Key Vault and should be retrieved from there
    key_vault_name = module.security.key_vault_name
    secrets = {
      database_connection_string = "database-connection-string"
      redis_connection_string   = "redis-connection-string"
      storage_connection_string = "storage-connection-string"
      azure_openai_api_key     = "azure-openai-api-key"
    }
  }
  sensitive = false
}

# Deployment information
output "deployment_info" {
  description = "Information needed for deployment"
  value = {
    resource_group_name       = azurerm_resource_group.main.name
    container_registry_server = module.container_registry.login_server
    container_app_environment = module.container_apps.container_app_environment_name
    backend_app_name         = module.container_apps.backend_app_name
    frontend_app_name        = module.container_apps.frontend_app_name
  }
}

# Resource IDs for reference
output "resource_ids" {
  description = "Resource IDs for reference"
  value = {
    resource_group_id              = azurerm_resource_group.main.id
    virtual_network_id            = module.network.virtual_network_id
    container_app_environment_id  = module.container_apps.container_app_environment_id
    database_server_id           = module.database.server_id
    redis_cache_id              = module.cache.cache_id
    storage_account_id          = module.storage.storage_account_id
    container_registry_id       = module.container_registry.registry_id
    key_vault_id               = module.security.key_vault_id
    log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
    application_insights_id    = module.monitoring.application_insights_id
  }
  sensitive = true
}

# Tags applied to resources
output "common_tags" {
  description = "Common tags applied to all resources"
  value       = local.common_tags
}