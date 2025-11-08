# Variables for Indian Legal AI Assistant Terraform configuration

variable "project_name" {
  description = "Name of the project, used as prefix for resources"
  type        = string
  default     = "legal-ai"
  
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "Central India"
  
  validation {
    condition = contains([
      "Central India",
      "South India",
      "West India",
      "East Asia",
      "Southeast Asia"
    ], var.location)
    error_message = "Location must be in India or nearby regions for data residency compliance."
  }
}

variable "database_admin_username" {
  description = "Administrator username for PostgreSQL server"
  type        = string
  default     = "legal_ai_admin"
  
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]+$", var.database_admin_username))
    error_message = "Database admin username must start with a letter and contain only letters, numbers, and underscores."
  }
}

variable "azure_openai_api_key" {
  description = "Azure OpenAI API key"
  type        = string
  sensitive   = true
  
  validation {
    condition     = length(var.azure_openai_api_key) > 0
    error_message = "Azure OpenAI API key is required."
  }
}

variable "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint URL"
  type        = string
  
  validation {
    condition     = can(regex("^https://.*\\.openai\\.azure\\.com/?$", var.azure_openai_endpoint))
    error_message = "Azure OpenAI endpoint must be a valid Azure OpenAI service URL."
  }
}

variable "container_image_tag" {
  description = "Container image tag to deploy"
  type        = string
  default     = "latest"
}

variable "enable_monitoring" {
  description = "Enable Application Insights and monitoring"
  type        = bool
  default     = true
}

variable "enable_auto_scale" {
  description = "Enable auto-scaling for container apps"
  type        = bool
  default     = true
}

variable "enable_high_availability" {
  description = "Enable high availability features (zone redundancy, geo-backup)"
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  description = "Number of days to retain database backups"
  type        = number
  default     = 7
  
  validation {
    condition     = var.backup_retention_days >= 7 && var.backup_retention_days <= 35
    error_message = "Backup retention days must be between 7 and 35."
  }
}

variable "allowed_ip_addresses" {
  description = "List of IP addresses allowed to access resources"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# Container Apps specific variables
variable "backend_cpu" {
  description = "CPU allocation for backend container"
  type        = number
  default     = 1.0
  
  validation {
    condition     = var.backend_cpu >= 0.25 && var.backend_cpu <= 4.0
    error_message = "Backend CPU must be between 0.25 and 4.0."
  }
}

variable "backend_memory" {
  description = "Memory allocation for backend container (in Gi)"
  type        = string
  default     = "2Gi"
  
  validation {
    condition     = can(regex("^[0-9]+(\\.[0-9]+)?Gi$", var.backend_memory))
    error_message = "Backend memory must be in format like '2Gi', '1.5Gi', etc."
  }
}

variable "frontend_cpu" {
  description = "CPU allocation for frontend container"
  type        = number
  default     = 0.5
  
  validation {
    condition     = var.frontend_cpu >= 0.25 && var.frontend_cpu <= 2.0
    error_message = "Frontend CPU must be between 0.25 and 2.0."
  }
}

variable "frontend_memory" {
  description = "Memory allocation for frontend container (in Gi)"
  type        = string
  default     = "1Gi"
  
  validation {
    condition     = can(regex("^[0-9]+(\\.[0-9]+)?Gi$", var.frontend_memory))
    error_message = "Frontend memory must be in format like '1Gi', '0.5Gi', etc."
  }
}

variable "min_replicas" {
  description = "Minimum number of container replicas"
  type        = number
  default     = 1
  
  validation {
    condition     = var.min_replicas >= 0 && var.min_replicas <= 10
    error_message = "Minimum replicas must be between 0 and 10."
  }
}

variable "max_replicas" {
  description = "Maximum number of container replicas"
  type        = number
  default     = 10
  
  validation {
    condition     = var.max_replicas >= 1 && var.max_replicas <= 30
    error_message = "Maximum replicas must be between 1 and 30."
  }
}

# Database specific variables
variable "database_sku_name" {
  description = "SKU name for PostgreSQL server"
  type        = string
  default     = null # Will be determined based on environment
}

variable "database_storage_gb" {
  description = "Storage size in GB for PostgreSQL server"
  type        = number
  default     = null # Will be determined based on environment
  
  validation {
    condition     = var.database_storage_gb == null || (var.database_storage_gb >= 32 && var.database_storage_gb <= 16384)
    error_message = "Database storage must be between 32 and 16384 GB."
  }
}

# Redis specific variables
variable "redis_sku_name" {
  description = "SKU name for Redis cache"
  type        = string
  default     = null # Will be determined based on environment
  
  validation {
    condition = var.redis_sku_name == null || contains([
      "Basic", "Standard", "Premium"
    ], var.redis_sku_name)
    error_message = "Redis SKU name must be one of: Basic, Standard, Premium."
  }
}

variable "redis_capacity" {
  description = "Capacity for Redis cache"
  type        = number
  default     = null # Will be determined based on environment
  
  validation {
    condition     = var.redis_capacity == null || (var.redis_capacity >= 0 && var.redis_capacity <= 6)
    error_message = "Redis capacity must be between 0 and 6."
  }
}