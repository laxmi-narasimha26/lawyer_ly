#!/bin/bash

# Build script for Indian Legal AI Assistant Docker images
# This script builds optimized production Docker images

set -e

# Configuration
REGISTRY="${DOCKER_REGISTRY:-legalai}"
VERSION="${VERSION:-$(git describe --tags --always --dirty)}"
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF=$(git rev-parse --short HEAD)

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

# Function to build an image
build_image() {
    local service=$1
    local context=$2
    local dockerfile=$3
    local image_name="${REGISTRY}/${service}:${VERSION}"
    local latest_name="${REGISTRY}/${service}:latest"
    
    log_info "Building ${service} image..."
    log_info "Context: ${context}"
    log_info "Dockerfile: ${dockerfile}"
    log_info "Image: ${image_name}"
    
    # Build the image
    docker build \
        --build-arg BUILD_DATE="${BUILD_DATE}" \
        --build-arg VERSION="${VERSION}" \
        --build-arg VCS_REF="${VCS_REF}" \
        --tag "${image_name}" \
        --tag "${latest_name}" \
        --file "${dockerfile}" \
        "${context}"
    
    if [ $? -eq 0 ]; then
        log_success "Successfully built ${service} image"
        
        # Display image size
        local size=$(docker images --format "table {{.Size}}" "${image_name}" | tail -n 1)
        log_info "Image size: ${size}"
        
        return 0
    else
        log_error "Failed to build ${service} image"
        return 1
    fi
}

# Function to run security scan
security_scan() {
    local image=$1
    
    if command -v trivy &> /dev/null; then
        log_info "Running security scan on ${image}..."
        trivy image --severity HIGH,CRITICAL "${image}"
    else
        log_warning "Trivy not found. Skipping security scan."
        log_warning "Install Trivy for security scanning: https://aquasecurity.github.io/trivy/"
    fi
}

# Function to test image
test_image() {
    local service=$1
    local image=$2
    
    log_info "Testing ${service} image..."
    
    case $service in
        "backend")
            # Test backend image
            docker run --rm "${image}" python -c "import main; print('Backend image test passed')"
            ;;
        "frontend")
            # Test frontend image (check if nginx starts)
            docker run --rm -d --name test-frontend "${image}"
            sleep 5
            if docker ps | grep -q test-frontend; then
                log_success "Frontend image test passed"
                docker stop test-frontend
            else
                log_error "Frontend image test failed"
                return 1
            fi
            ;;
    esac
}

# Main build process
main() {
    log_info "Starting Docker build process..."
    log_info "Registry: ${REGISTRY}"
    log_info "Version: ${VERSION}"
    log_info "Build Date: ${BUILD_DATE}"
    log_info "VCS Ref: ${VCS_REF}"
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    
    # Check if we're in the project root
    if [ ! -f "docker-compose.yml" ]; then
        log_error "Please run this script from the project root directory."
        exit 1
    fi
    
    # Build backend image
    if build_image "backend" "./backend" "./backend/Dockerfile"; then
        security_scan "${REGISTRY}/backend:${VERSION}"
        test_image "backend" "${REGISTRY}/backend:${VERSION}"
    else
        log_error "Backend build failed"
        exit 1
    fi
    
    # Build frontend image
    if build_image "frontend" "./frontend" "./frontend/Dockerfile"; then
        security_scan "${REGISTRY}/frontend:${VERSION}"
        test_image "frontend" "${REGISTRY}/frontend:${VERSION}"
    else
        log_error "Frontend build failed"
        exit 1
    fi
    
    # Display summary
    log_success "All images built successfully!"
    echo
    log_info "Built images:"
    docker images | grep "${REGISTRY}" | grep -E "(${VERSION}|latest)"
    
    echo
    log_info "To push images to registry:"
    echo "  docker push ${REGISTRY}/backend:${VERSION}"
    echo "  docker push ${REGISTRY}/backend:latest"
    echo "  docker push ${REGISTRY}/frontend:${VERSION}"
    echo "  docker push ${REGISTRY}/frontend:latest"
    
    echo
    log_info "To run locally:"
    echo "  docker-compose up -d"
    
    echo
    log_info "To deploy to production:"
    echo "  docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --no-cache)
            DOCKER_BUILD_ARGS="--no-cache"
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo
            echo "Options:"
            echo "  --registry REGISTRY    Docker registry prefix (default: legalai)"
            echo "  --version VERSION      Image version tag (default: git describe)"
            echo "  --no-cache            Build without using cache"
            echo "  --help                Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main