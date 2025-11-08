# Main Terraform configuration for Indian Legal AI Assistant
# This file defines the core infrastructure resources

terraform {
  required_version = ">= 1.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.4"
    }
  }
  
  # Backend configuration for state storage
  # Uncomment and configure for production use
  # backend "azurerm" {
  #   resource_group_name  = "terraform-state-rg"
  #   storage_account_name = "terraformstatestorage"
  #   container_name       = "tfstate"
  #   key                  = "legal-ai.terraform.tfstate"
  # }
}

# Configure the Azure Provider
provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = true
      recover_soft_deleted_key_vaults = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

# Data sources
data "azurerm_client_config" "current" {}

# Local values
locals {
  resource_prefix = "${var.project_name}-${var.environment}"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    CreatedDate = formatdate("YYYY-MM-DD", timestamp())
  }
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = "${local.resource_prefix}-rg"
  location = var.location
  tags     = local.common_tags
}

# Random password for database
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# Network module
module "network" {
  source = "./modules/network"
  
  resource_group_name = azurerm_resource_group.main.name
  location           = azurerm_resource_group.main.location
  resource_prefix    = local.resource_prefix
  tags              = local.common_tags
}

# Security module (Key Vault)
module "security" {
  source = "./modules/security"
  
  resource_group_name = azurerm_resource_group.main.name
  location           = azurerm_resource_group.main.location
  resource_prefix    = local.resource_prefix
  tags              = local.common_tags
  
  tenant_id                    = data.azurerm_client_config.current.tenant_id
  azure_openai_api_key        = var.azure_openai_api_key
  database_admin_password     = random_password.db_password.result
}

# Monitoring module
module "monitoring" {
  source = "./modules/monitoring"
  
  resource_group_name = azurerm_resource_group.main.name
  location           = azurerm_resource_group.main.location
  resource_prefix    = local.resource_prefix
  tags              = local.common_tags
  
  enable_monitoring = var.enable_monitoring
}

# Storage module
module "storage" {
  source = "./modules/storage"
  
  resource_group_name = azurerm_resource_group.main.name
  location           = azurerm_resource_group.main.location
  resource_prefix    = local.resource_prefix
  tags              = local.common_tags
  
  virtual_network_id         = module.network.virtual_network_id
  private_endpoint_subnet_id = module.network.private_endpoint_subnet_id
}

# Database module
module "database" {
  source = "./modules/database"
  
  resource_group_name = azurerm_resource_group.main.name
  location           = azurerm_resource_group.main.location
  resource_prefix    = local.resource_prefix
  tags              = local.common_tags
  
  administrator_login         = var.database_admin_username
  administrator_password      = random_password.db_password.result
  environment                = var.environment
  virtual_network_id         = module.network.virtual_network_id
  private_endpoint_subnet_id = module.network.private_endpoint_subnet_id
}

# Cache module (Redis)
module "cache" {
  source = "./modules/cache"
  
  resource_group_name = azurerm_resource_group.main.name
  location           = azurerm_resource_group.main.location
  resource_prefix    = local.resource_prefix
  tags              = local.common_tags
  
  environment                = var.environment
  virtual_network_id         = module.network.virtual_network_id
  private_endpoint_subnet_id = module.network.private_endpoint_subnet_id
}

# Container Registry module
module "container_registry" {
  source = "./modules/container_registry"
  
  resource_group_name = azurerm_resource_group.main.name
  location           = azurerm_resource_group.main.location
  resource_prefix    = local.resource_prefix
  tags              = local.common_tags
}

# Container Apps module
module "container_apps" {
  source = "./modules/container_apps"
  
  resource_group_name = azurerm_resource_group.main.name
  location           = azurerm_resource_group.main.location
  resource_prefix    = local.resource_prefix
  tags              = local.common_tags
  
  # Dependencies
  subnet_id                           = module.network.container_apps_subnet_id
  log_analytics_workspace_id          = module.monitoring.log_analytics_workspace_id
  application_insights_connection_string = module.monitoring.application_insights_connection_string
  container_registry_server           = module.container_registry.login_server
  key_vault_name                     = module.security.key_vault_name
  
  # Configuration
  container_image_tag    = var.container_image_tag
  azure_openai_endpoint  = var.azure_openai_endpoint
  enable_auto_scale     = var.enable_auto_scale
  
  # Connection strings (will be stored in Key Vault)
  database_connection_string = module.database.connection_string
  redis_connection_string   = module.cache.connection_string
  storage_connection_string = module.storage.connection_string
}

# Store connection strings in Key Vault
resource "azurerm_key_vault_secret" "database_connection_string" {
  name         = "database-connection-string"
  value        = module.database.connection_string
  key_vault_id = module.security.key_vault_id
  
  depends_on = [module.security]
}

resource "azurerm_key_vault_secret" "redis_connection_string" {
  name         = "redis-connection-string"
  value        = module.cache.connection_string
  key_vault_id = module.security.key_vault_id
  
  depends_on = [module.security]
}

resource "azurerm_key_vault_secret" "storage_connection_string" {
  name         = "storage-connection-string"
  value        = module.storage.connection_string
  key_vault_id = module.security.key_vault_id
  
  depends_on = [module.security]
}