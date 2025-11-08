#!/bin/bash

# Infrastructure deployment script for Indian Legal AI Assistant
# Supports both ARM templates and Terraform

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INFRASTRUCTURE_DIR="$PROJECT_ROOT/infrastructure"

# Default values
DEPLOYMENT_METHOD="terraform"
ENVIRONMENT="dev"
LOCATION="Central India"
PROJECT_NAME="legal-ai"
RESOURCE_GROUP=""
SUBSCRIPTION_ID=""
TENANT_ID=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show help
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy infrastructure for Indian Legal AI Assistant

OPTIONS:
    -m, --method METHOD         Deployment method: terraform or arm (default: terraform)
    -e, --environment ENV       Environment: dev, staging, prod (default: dev)
    -l, --location LOCATION     Azure region (default: Central India)
    -p, --project PROJECT       Project name (default: legal-ai)
    -g, --resource-group RG     Resource group name (auto-generated if not provided)
    -s, --subscription ID       Azure subscription ID
    -t, --tenant ID            Azure tenant ID
    --azure-openai-key KEY     Azure OpenAI API key (required)
    --azure-openai-endpoint URL Azure OpenAI endpoint URL (required)
    --destroy                  Destroy infrastructure instead of creating
    --plan-only                Show deployment plan without applying (Terraform only)
    --auto-approve             Auto-approve deployment without confirmation
    -h, --help                 Show this help message

EXAMPLES:
    # Deploy using Terraform (default)
    $0 --environment prod --azure-openai-key "your-key" --azure-openai-endpoint "https://your-endpoint.openai.azure.com"
    
    # Deploy using ARM templates
    $0 --method arm --environment staging --azure-openai-key "your-key" --azure-openai-endpoint "https://your-endpoint.openai.azure.com"
    
    # Show Terraform plan only
    $0 --plan-only --environment prod
    
    # Destroy infrastructure
    $0 --destroy --environment dev --auto-approve

PREREQUISITES:
    - Azure CLI installed and logged in
    - Terraform installed (if using Terraform method)
    - Appropriate Azure permissions for resource creation
    - Azure OpenAI service provisioned

EOF
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Azure CLI
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check Azure login
    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure. Please run 'az login' first."
        exit 1
    fi
    
    # Check Terraform if using Terraform method
    if [ "$DEPLOYMENT_METHOD" = "terraform" ]; then
        if ! command -v terraform &> /dev/null; then
            log_error "Terraform is not installed. Please install it first."
            exit 1
        fi
    fi
    
    # Check required parameters
    if [ -z "$AZURE_OPENAI_API_KEY" ]; then
        log_error "Azure OpenAI API key is required. Use --azure-openai-key parameter."
        exit 1
    fi
    
    if [ -z "$AZURE_OPENAI_ENDPOINT" ]; then
        log_error "Azure OpenAI endpoint is required. Use --azure-openai-endpoint parameter."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Function to set Azure context
set_azure_context() {
    if [ -n "$SUBSCRIPTION_ID" ]; then
        log_info "Setting Azure subscription to $SUBSCRIPTION_ID"
        az account set --subscription "$SUBSCRIPTION_ID"
    fi
    
    # Get current subscription info
    CURRENT_SUBSCRIPTION=$(az account show --query "id" -o tsv)
    CURRENT_TENANT=$(az account show --query "tenantId" -o tsv)
    
    log_info "Using Azure subscription: $CURRENT_SUBSCRIPTION"
    log_info "Using Azure tenant: $CURRENT_TENANT"
    
    # Set defaults if not provided
    if [ -z "$SUBSCRIPTION_ID" ]; then
        SUBSCRIPTION_ID="$CURRENT_SUBSCRIPTION"
    fi
    
    if [ -z "$TENANT_ID" ]; then
        TENANT_ID="$CURRENT_TENANT"
    fi
}

# Function to generate resource group name
generate_resource_group_name() {
    if [ -z "$RESOURCE_GROUP" ]; then
        RESOURCE_GROUP="${PROJECT_NAME}-${ENVIRONMENT}-rg"
    fi
    log_info "Using resource group: $RESOURCE_GROUP"
}

# Function to deploy using Terraform
deploy_terraform() {
    log_info "Deploying infrastructure using Terraform..."
    
    cd "$INFRASTRUCTURE_DIR/terraform"
    
    # Initialize Terraform
    log_info "Initializing Terraform..."
    terraform init
    
    # Create terraform.tfvars file
    cat > terraform.tfvars << EOF
project_name = "$PROJECT_NAME"
environment = "$ENVIRONMENT"
location = "$LOCATION"
azure_openai_api_key = "$AZURE_OPENAI_API_KEY"
azure_openai_endpoint = "$AZURE_OPENAI_ENDPOINT"
enable_monitoring = true
enable_auto_scale = $([ "$ENVIRONMENT" = "prod" ] && echo "true" || echo "false")
enable_high_availability = $([ "$ENVIRONMENT" = "prod" ] && echo "true" || echo "false")
EOF
    
    if [ "$DESTROY" = "true" ]; then
        log_warning "Destroying infrastructure..."
        if [ "$AUTO_APPROVE" = "true" ]; then
            terraform destroy -auto-approve
        else
            terraform destroy
        fi
        log_success "Infrastructure destroyed successfully"
    elif [ "$PLAN_ONLY" = "true" ]; then
        log_info "Showing Terraform plan..."
        terraform plan
    else
        # Plan
        log_info "Creating Terraform plan..."
        terraform plan -out=tfplan
        
        # Apply
        if [ "$AUTO_APPROVE" = "true" ]; then
            log_info "Applying Terraform plan..."
            terraform apply -auto-approve tfplan
        else
            log_info "Applying Terraform plan..."
            terraform apply tfplan
        fi
        
        # Show outputs
        log_success "Infrastructure deployed successfully!"
        echo
        log_info "Deployment outputs:"
        terraform output
        
        # Save outputs to file
        terraform output -json > "$PROJECT_ROOT/terraform-outputs.json"
        log_info "Outputs saved to terraform-outputs.json"
    fi
}

# Function to deploy using ARM templates
deploy_arm() {
    log_info "Deploying infrastructure using ARM templates..."
    
    # Create resource group
    log_info "Creating resource group: $RESOURCE_GROUP"
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
    
    # Generate deployment name
    DEPLOYMENT_NAME="${PROJECT_NAME}-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S)"
    
    # Create parameters file
    PARAMS_FILE="$INFRASTRUCTURE_DIR/azure/arm/parameters.json"
    cat > "$PARAMS_FILE" << EOF
{
  "\$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "projectName": {
      "value": "$PROJECT_NAME"
    },
    "environment": {
      "value": "$ENVIRONMENT"
    },
    "location": {
      "value": "$LOCATION"
    },
    "administratorLogin": {
      "value": "legal_ai_admin"
    },
    "administratorLoginPassword": {
      "value": "$(openssl rand -base64 32)"
    },
    "openAiApiKey": {
      "value": "$AZURE_OPENAI_API_KEY"
    },
    "openAiEndpoint": {
      "value": "$AZURE_OPENAI_ENDPOINT"
    },
    "enableMonitoring": {
      "value": true
    },
    "enableAutoScale": {
      "value": $([ "$ENVIRONMENT" = "prod" ] && echo "true" || echo "false")
    }
  }
}
EOF
    
    if [ "$DESTROY" = "true" ]; then
        log_warning "Destroying resource group: $RESOURCE_GROUP"
        if [ "$AUTO_APPROVE" = "true" ]; then
            az group delete --name "$RESOURCE_GROUP" --yes --no-wait
        else
            az group delete --name "$RESOURCE_GROUP"
        fi
        log_success "Infrastructure destruction initiated"
    else
        # Deploy ARM template
        log_info "Deploying ARM template..."
        az deployment group create \
            --resource-group "$RESOURCE_GROUP" \
            --name "$DEPLOYMENT_NAME" \
            --template-file "$INFRASTRUCTURE_DIR/azure/arm/main.json" \
            --parameters "@$PARAMS_FILE"
        
        # Show outputs
        log_success "Infrastructure deployed successfully!"
        echo
        log_info "Deployment outputs:"
        az deployment group show \
            --resource-group "$RESOURCE_GROUP" \
            --name "$DEPLOYMENT_NAME" \
            --query "properties.outputs" \
            --output table
        
        # Save outputs to file
        az deployment group show \
            --resource-group "$RESOURCE_GROUP" \
            --name "$DEPLOYMENT_NAME" \
            --query "properties.outputs" > "$PROJECT_ROOT/arm-outputs.json"
        log_info "Outputs saved to arm-outputs.json"
    fi
}

# Main deployment function
main() {
    log_info "Starting infrastructure deployment..."
    log_info "Method: $DEPLOYMENT_METHOD"
    log_info "Environment: $ENVIRONMENT"
    log_info "Location: $LOCATION"
    log_info "Project: $PROJECT_NAME"
    
    check_prerequisites
    set_azure_context
    generate_resource_group_name
    
    case $DEPLOYMENT_METHOD in
        "terraform")
            deploy_terraform
            ;;
        "arm")
            deploy_arm
            ;;
        *)
            log_error "Unknown deployment method: $DEPLOYMENT_METHOD"
            exit 1
            ;;
    esac
    
    log_success "Deployment completed successfully!"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--method)
            DEPLOYMENT_METHOD="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -l|--location)
            LOCATION="$2"
            shift 2
            ;;
        -p|--project)
            PROJECT_NAME="$2"
            shift 2
            ;;
        -g|--resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        -s|--subscription)
            SUBSCRIPTION_ID="$2"
            shift 2
            ;;
        -t|--tenant)
            TENANT_ID="$2"
            shift 2
            ;;
        --azure-openai-key)
            AZURE_OPENAI_API_KEY="$2"
            shift 2
            ;;
        --azure-openai-endpoint)
            AZURE_OPENAI_ENDPOINT="$2"
            shift 2
            ;;
        --destroy)
            DESTROY="true"
            shift
            ;;
        --plan-only)
            PLAN_ONLY="true"
            shift
            ;;
        --auto-approve)
            AUTO_APPROVE="true"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate deployment method
if [[ ! "$DEPLOYMENT_METHOD" =~ ^(terraform|arm)$ ]]; then
    log_error "Invalid deployment method: $DEPLOYMENT_METHOD. Must be 'terraform' or 'arm'."
    exit 1
fi

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    log_error "Invalid environment: $ENVIRONMENT. Must be 'dev', 'staging', or 'prod'."
    exit 1
fi

# Run main function
main