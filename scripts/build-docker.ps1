# Build script for Indian Legal AI Assistant Docker images
# PowerShell version for Windows environments

param(
    [string]$Registry = "legalai",
    [string]$Version = "",
    [switch]$NoCache,
    [switch]$Help
)

# Configuration
if (-not $Version) {
    try {
        $Version = git describe --tags --always --dirty 2>$null
        if (-not $Version) {
            $Version = git rev-parse --short HEAD 2>$null
            if (-not $Version) {
                $Version = "latest"
            }
        }
    }
    catch {
        $Version = "latest"
    }
}

$BuildDate = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
try {
    $VcsRef = git rev-parse --short HEAD 2>$null
    if (-not $VcsRef) {
        $VcsRef = "unknown"
    }
}
catch {
    $VcsRef = "unknown"
}

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
    Write-Host "Usage: .\build-docker.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Registry REGISTRY    Docker registry prefix (default: legalai)"
    Write-Host "  -Version VERSION      Image version tag (default: git describe)"
    Write-Host "  -NoCache             Build without using cache"
    Write-Host "  -Help                Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\build-docker.ps1"
    Write-Host "  .\build-docker.ps1 -Registry myregistry -Version 1.0.0"
    Write-Host "  .\build-docker.ps1 -NoCache"
}

# Function to build an image
function Build-Image {
    param(
        [string]$Service,
        [string]$Context,
        [string]$Dockerfile
    )
    
    $ImageName = "$Registry/${Service}:$Version"
    $LatestName = "$Registry/${Service}:latest"
    
    Write-Info "Building $Service image..."
    Write-Info "Context: $Context"
    Write-Info "Dockerfile: $Dockerfile"
    Write-Info "Image: $ImageName"
    
    # Prepare build arguments
    $BuildArgs = @(
        "build",
        "--build-arg", "BUILD_DATE=$BuildDate",
        "--build-arg", "VERSION=$Version",
        "--build-arg", "VCS_REF=$VcsRef",
        "--tag", $ImageName,
        "--tag", $LatestName,
        "--file", $Dockerfile
    )
    
    if ($NoCache) {
        $BuildArgs += "--no-cache"
    }
    
    $BuildArgs += $Context
    
    # Build the image
    $Process = Start-Process -FilePath "docker" -ArgumentList $BuildArgs -Wait -PassThru -NoNewWindow
    
    if ($Process.ExitCode -eq 0) {
        Write-Success "Successfully built $Service image"
        
        # Display image size
        $SizeOutput = docker images --format "table {{.Size}}" $ImageName | Select-Object -Skip 1
        Write-Info "Image size: $SizeOutput"
        
        return $true
    }
    else {
        Write-Error "Failed to build $Service image"
        return $false
    }
}

# Function to run security scan
function Start-SecurityScan {
    param([string]$Image)
    
    if (Get-Command trivy -ErrorAction SilentlyContinue) {
        Write-Info "Running security scan on $Image..."
        trivy image --severity HIGH,CRITICAL $Image
    }
    else {
        Write-Warning "Trivy not found. Skipping security scan."
        Write-Warning "Install Trivy for security scanning: https://aquasecurity.github.io/trivy/"
    }
}

# Function to test image
function Test-Image {
    param(
        [string]$Service,
        [string]$Image
    )
    
    Write-Info "Testing $Service image..."
    
    switch ($Service) {
        "backend" {
            # Test backend image
            $TestResult = docker run --rm $Image python -c "import main; print('Backend image test passed')" 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Backend image test passed"
                return $true
            }
            else {
                Write-Error "Backend image test failed"
                return $false
            }
        }
        "frontend" {
            # Test frontend image (check if nginx starts)
            docker run --rm -d --name test-frontend $Image | Out-Null
            Start-Sleep -Seconds 5
            
            $ContainerRunning = docker ps --filter "name=test-frontend" --format "{{.Names}}" | Where-Object { $_ -eq "test-frontend" }
            
            if ($ContainerRunning) {
                Write-Success "Frontend image test passed"
                docker stop test-frontend | Out-Null
                return $true
            }
            else {
                Write-Error "Frontend image test failed"
                return $false
            }
        }
    }
}

# Main build process
function Start-Build {
    Write-Info "Starting Docker build process..."
    Write-Info "Registry: $Registry"
    Write-Info "Version: $Version"
    Write-Info "Build Date: $BuildDate"
    Write-Info "VCS Ref: $VcsRef"
    
    # Check if Docker is running
    try {
        docker info | Out-Null
    }
    catch {
        Write-Error "Docker is not running. Please start Docker and try again."
        exit 1
    }
    
    # Check if we're in the project root
    if (-not (Test-Path "docker-compose.yml")) {
        Write-Error "Please run this script from the project root directory."
        exit 1
    }
    
    # Build backend image
    if (Build-Image -Service "backend" -Context "./backend" -Dockerfile "./backend/Dockerfile") {
        Start-SecurityScan -Image "$Registry/backend:$Version"
        if (-not (Test-Image -Service "backend" -Image "$Registry/backend:$Version")) {
            Write-Error "Backend image test failed"
            exit 1
        }
    }
    else {
        Write-Error "Backend build failed"
        exit 1
    }
    
    # Build frontend image
    if (Build-Image -Service "frontend" -Context "./frontend" -Dockerfile "./frontend/Dockerfile") {
        Start-SecurityScan -Image "$Registry/frontend:$Version"
        if (-not (Test-Image -Service "frontend" -Image "$Registry/frontend:$Version")) {
            Write-Error "Frontend image test failed"
            exit 1
        }
    }
    else {
        Write-Error "Frontend build failed"
        exit 1
    }
    
    # Display summary
    Write-Success "All images built successfully!"
    Write-Host ""
    Write-Info "Built images:"
    docker images | Where-Object { $_ -match $Registry -and ($_ -match $Version -or $_ -match "latest") }
    
    Write-Host ""
    Write-Info "To push images to registry:"
    Write-Host "  docker push $Registry/backend:$Version"
    Write-Host "  docker push $Registry/backend:latest"
    Write-Host "  docker push $Registry/frontend:$Version"
    Write-Host "  docker push $Registry/frontend:latest"
    
    Write-Host ""
    Write-Info "To run locally:"
    Write-Host "  docker-compose up -d"
    
    Write-Host ""
    Write-Info "To deploy to production:"
    Write-Host "  docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
}

# Main execution
if ($Help) {
    Show-Help
    exit 0
}

Start-Build