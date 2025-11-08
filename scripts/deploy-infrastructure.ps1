# Infrastructure deployment script for Indian Legal AI Assistant
# PowerShell version for Windows environments

param(
    [string]$Method = "terraform",
    [string]$Environment = "dev",
    [string]$Location = "Central India",
    [string]$ProjectName = "legal-ai",
    [string]$ResourceGroup = "",
    [string]$SubscriptionId = "",
    [string]$TenantId = "",
    [string]$AzureOpenAiKey = "",
    [string]$AzureOpenAiEndpoint = "",
    [switch]$Destroy,
    [switch]$PlanOnly,
    [switch]$AutoApprove,
    [switch]$Help
)

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$InfrastructureDir = Join-Path $ProjectRoot "infrastructure"

# Colors for output
$Colors = @{
    Red = "Red"
    Green = "Green"
    Yellow = "Yellow"
    Blue = "Blue"
    White = "White"
}

# Logging functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor $Colors.Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor $Colors.Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor $Colors.Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor $Colors.Red
}

# Function to show help
function Show-Help {
    Write-Host @"
Usage: .\deploy-infrastructure.ps1 [OPTIONS]

Deploy infrastructure for Indian Legal AI Assistant

OPTIONS:
    -Method METHOD              Deployment method: terraform or arm (default: terraform)
    -Environment ENV            Environment: dev, staging, prod (default: dev)
    -Location LOCATION          Azure region (default: Central India)
    -ProjectName PROJECT        Project name (default: legal-ai)
    -ResourceGroup RG           Resource group name (auto-generated if not provided)
    -SubscriptionId ID          Azure subscription ID
    -TenantId ID               Azure tenant ID
    -AzureOpenAiKey KEY        Azure OpenAI API key (required)
    -AzureOpenAiEndpoint URL   Azure OpenAI endpoint URL (required)
    -Destroy                   Destroy infrastructure instead of creating
    -PlanOnly                  Show deployment plan without applying (Terraform only)
    -AutoApprove               Auto-approve deployment without confirmation
    -Help                      Show this help message

EXAMPLES:
    # Deploy using Terraform (default)
    .\deploy-infrastructure.ps1 -Environment prod -AzureOpenAiKey "your-key" -AzureOpenAiEndpoint "https://your-endpoint.openai.azure.com"
    
    # Deploy using ARM templates
    .\deploy-infrastructure.ps1 -Method arm -Environment staging -AzureOpenAiKey "your-key" -AzureOpenAiEndpoint "https://your-endpoint.openai.azure.com"
    
    # Show Terraform plan only
    .\deploy-infrastructure.ps1 -PlanOnly -Environment prod
    
    # Destroy infrastructure
    .\deploy-infrastructure.ps1 -Destroy -Environment dev -AutoApprove

PREREQUISITES:
    - Azure CLI installed and logged in
    - Terraform installed (if using Terraform method)
    - Appropriate Azure permissions for resource creation
    - Azure OpenAI service provisioned
"@
}

# Function to check prerequisites
function Test-Prerequisites {
    Write-Info "Checking prerequisites..."
    
    # Check Azure CLI
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        Write-Error "Azure CLI is not installed. Please install it first."
        exit 1
    }
    
    # Check Azure login
    try {
        az account show | Out-Null
    }
    catch {
        Write-Error "Not logged in to Azure. Please run 'az login' first."
        exit 1
    }
    
    # Check Terraform if using Terraform method
    if ($Method -eq "terraform") {
        if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) {
            Write-Error "Terraform is not installed. Please install it first."
            exit 1
        }
    }
    
    # Check required parameters
    if (-not $AzureOpenAiKey) {
        Write-Error "Azure OpenAI API key is required. Use -AzureOpenAiKey parameter."
        exit 1
    }
    
    if (-not $AzureOpenAiEndpoint) {
        Write-Error "Azure OpenAI endpoint is required. Use -AzureOpenAiEndpoint parameter."
        exit 1
    }
    
    Write-Success "Prerequisites check passed"
}

# Function to set Azure context
function Set-AzureContext {
    if ($SubscriptionId) {
        Write-Info "Setting Azure subscription to $SubscriptionId"
        az account set --subscription $SubscriptionId
    }
    
    # Get current subscription info
    $CurrentSubscription = az account show --query "id" -o tsv
    $CurrentTenant = az account show --query "tenantId" -o tsv
    
    Write-Info "Using Azure subscription: $CurrentSubscription"
    Write-Info "Using Azure tenant: $CurrentTenant"
    
    # Set defaults if not provided
    if (-not $SubscriptionId) {
        $script:SubscriptionId = $CurrentSubscription
    }
    
    if (-not $TenantId) {
        $script:TenantId = $CurrentTenant
    }
}

# Function to generate resource group name
function Set-ResourceGroupName {
    if (-not $ResourceGroup) {
        $script:ResourceGroup = "$ProjectName-$Environment-rg"
    }
    Write-Info "Using resource group: $ResourceGroup"
}

# Function to deploy using Terraform
function Deploy-Terraform {
    Write-Info "Deploying infrastructure using Terraform..."
    
    $TerraformDir = Join-Path $InfrastructureDir "terraform"
    Set-Location $TerraformDir
    
    # Initialize Terraform
    Write-Info "Initializing Terraform..."
    terraform init
    
    # Create terraform.tfvars file
    $TfVarsContent = @"
project_name = "$ProjectName"
environment = "$Environment"
location = "$Location"
azure_openai_api_key = "$AzureOpenAiKey"
azure_openai_endpoint = "$AzureOpenAiEndpoint"
enable_monitoring = true
enable_auto_scale = $($Environment -eq "prod" ? "true" : "false")
enable_high_availability = $($Environment -eq "prod" ? "true" : "false")
"@
    
    $TfVarsContent | Out-File -FilePath "terraform.tfvars" -Encoding UTF8
    
    if ($Destroy) {
        Write-Warning "Destroying infrastructure..."
        if ($AutoApprove) {
            terraform destroy -auto-approve
        }
        else {
            terraform destroy
        }
        Write-Success "Infrastructure destroyed successfully"
    }
    elseif ($PlanOnly) {
        Write-Info "Showing Terraform plan..."
        terraform plan
    }
    else {
        # Plan
        Write-Info "Creating Terraform plan..."
        terraform plan -out=tfplan
        
        # Apply
        if ($AutoApprove) {
            Write-Info "Applying Terraform plan..."
            terraform apply -auto-approve tfplan
        }
        else {
            Write-Info "Applying Terraform plan..."
            terraform apply tfplan
        }
        
        # Show outputs
        Write-Success "Infrastructure deployed successfully!"
        Write-Host ""
        Write-Info "Deployment outputs:"
        terraform output
        
        # Save outputs to file
        $OutputFile = Join-Path $ProjectRoot "terraform-outputs.json"
        terraform output -json | Out-File -FilePath $OutputFile -Encoding UTF8
        Write-Info "Outputs saved to terraform-outputs.json"
    }
}

# Function to deploy using ARM templates
function Deploy-ARM {
    Write-Info "Deploying infrastructure using ARM templates..."
    
    # Create resource group
    Write-Info "Creating resource group: $ResourceGroup"
    az group create --name $ResourceGroup --location $Location
    
    # Generate deployment name
    $DeploymentName = "$ProjectName-$Environment-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    
    # Create parameters file
    $ArmDir = Join-Path $InfrastructureDir "azure\arm"
    $ParamsFile = Join-Path $ArmDir "parameters.json"
    
    $RandomPassword = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
    
    $ParamsContent = @{
        '$schema' = "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#"
        contentVersion = "1.0.0.0"
        parameters = @{
            projectName = @{ value = $ProjectName }
            environment = @{ value = $Environment }
            location = @{ value = $Location }
            administratorLogin = @{ value = "legal_ai_admin" }
            administratorLoginPassword = @{ value = $RandomPassword }
            openAiApiKey = @{ value = $AzureOpenAiKey }
            openAiEndpoint = @{ value = $AzureOpenAiEndpoint }
            enableMonitoring = @{ value = $true }
            enableAutoScale = @{ value = ($Environment -eq "prod") }
        }
    }
    
    $ParamsContent | ConvertTo-Json -Depth 10 | Out-File -FilePath $ParamsFile -Encoding UTF8
    
    if ($Destroy) {
        Write-Warning "Destroying resource group: $ResourceGroup"
        if ($AutoApprove) {
            az group delete --name $ResourceGroup --yes --no-wait
        }
        else {
            az group delete --name $ResourceGroup
        }
        Write-Success "Infrastructure destruction initiated"
    }
    else {
        # Deploy ARM template
        Write-Info "Deploying ARM template..."
        $MainTemplate = Join-Path $ArmDir "main.json"
        
        az deployment group create `
            --resource-group $ResourceGroup `
            --name $DeploymentName `
            --template-file $MainTemplate `
            --parameters "@$ParamsFile"
        
        # Show outputs
        Write-Success "Infrastructure deployed successfully!"
        Write-Host ""
        Write-Info "Deployment outputs:"
        az deployment group show `
            --resource-group $ResourceGroup `
            --name $DeploymentName `
            --query "properties.outputs" `
            --output table
        
        # Save outputs to file
        $OutputFile = Join-Path $ProjectRoot "arm-outputs.json"
        az deployment group show `
            --resource-group $ResourceGroup `
            --name $DeploymentName `
            --query "properties.outputs" | Out-File -FilePath $OutputFile -Encoding UTF8
        Write-Info "Outputs saved to arm-outputs.json"
    }
}

# Main deployment function
function Start-Deployment {
    Write-Info "Starting infrastructure deployment..."
    Write-Info "Method: $Method"
    Write-Info "Environment: $Environment"
    Write-Info "Location: $Location"
    Write-Info "Project: $ProjectName"
    
    Test-Prerequisites
    Set-AzureContext
    Set-ResourceGroupName
    
    switch ($Method) {
        "terraform" {
            Deploy-Terraform
        }
        "arm" {
            Deploy-ARM
        }
        default {
            Write-Error "Unknown deployment method: $Method"
            exit 1
        }
    }
    
    Write-Success "Deployment completed successfully!"
}

# Main execution
if ($Help) {
    Show-Help
    exit 0
}

# Validate deployment method
if ($Method -notin @("terraform", "arm")) {
    Write-Error "Invalid deployment method: $Method. Must be 'terraform' or 'arm'."
    exit 1
}

# Validate environment
if ($Environment -notin @("dev", "staging", "prod")) {
    Write-Error "Invalid environment: $Environment. Must be 'dev', 'staging', or 'prod'."
    exit 1
}

# Run main function
Start-Deployment