#!/bin/bash
# ============================================================================
# Azure Deployment Script
# ============================================================================
# Automates deployment of Spreadsheet app to Azure App Service
#
# Prerequisites:
#   - Azure CLI installed and authenticated: az login
#   - Docker installed and running
#   - Sufficient Azure permissions to create resources
#
# Usage:
#   ./scripts/azure-deploy.sh [env] [license-key] [app-name]
#
# Examples:
#   ./scripts/azure-deploy.sh dev "YOUR_LICENSE_KEY"
#   ./scripts/azure-deploy.sh prod "YOUR_LICENSE_KEY" "myapp"
#
# ============================================================================

set -e

# ---- Configuration ----
ENVIRONMENT=${1:-"dev"}
LICENSE_KEY=${2:-""}
APP_BASE_NAME=${3:-"spreadsheet-app"}

LOCATION="eastus"
RESOURCE_GROUP="rg-${APP_BASE_NAME}-${ENVIRONMENT}"
ACR_NAME="${APP_BASE_NAME//-/}acr${ENVIRONMENT:0:1}"
REDIS_NAME="${APP_BASE_NAME}-redis-${ENVIRONMENT}"
APP_SERVICE_PLAN="${APP_BASE_NAME}-plan-${ENVIRONMENT}"
APP_SERVICE="${APP_BASE_NAME}-${ENVIRONMENT}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---- Functions ----
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ---- Validation ----
if [ -z "$LICENSE_KEY" ]; then
    log_error "Syncfusion license key is required"
    echo "Usage: $0 <env> <license-key> [app-name]"
    exit 1
fi

# Check if Docker is running
if ! docker ps &>/dev/null; then
    log_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if Azure CLI is available
if ! command -v az &>/dev/null; then
    log_error "Azure CLI is not installed. Visit: https://learn.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# ---- Header ----
clear
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     Spreadsheet App - Azure Deployment Script                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Configuration:"
echo "  Environment:       $ENVIRONMENT"
echo "  Location:          $LOCATION"
echo "  Resource Group:    $RESOURCE_GROUP"
echo "  Container Registry: $ACR_NAME"
echo "  Redis Cache:       $REDIS_NAME"
echo "  App Service:       $APP_SERVICE"
echo ""

# ---- Step 1: Create Resource Group ----
log_info "Step 1: Creating Azure Resource Group..."
if az group exists --name "$RESOURCE_GROUP" | grep -q "true"; then
    log_warn "Resource group already exists: $RESOURCE_GROUP"
else
    az group create \
        --name "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --output none
    log_success "Resource group created: $RESOURCE_GROUP"
fi

# ---- Step 2: Create Container Registry ----
log_info "Step 2: Setting up Azure Container Registry..."
if az acr show --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" &>/dev/null; then
    log_warn "Container registry already exists: $ACR_NAME"
else
    az acr create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$ACR_NAME" \
        --sku Basic \
        --output none
    log_success "Container registry created: $ACR_NAME"
fi

# ---- Step 3: Create Redis Cache ----
log_info "Step 3: Creating Azure Redis Cache..."
if az redis show --resource-group "$RESOURCE_GROUP" --name "$REDIS_NAME" &>/dev/null; then
    log_warn "Redis cache already exists: $REDIS_NAME"
else
    az redis create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$REDIS_NAME" \
        --location "$LOCATION" \
        --sku Basic \
        --vm-size c0 \
        --minimum-tls-version 1.2 \
        --output none
    log_success "Redis cache created: $REDIS_NAME"
fi

# ---- Step 4: Create App Service Plan ----
log_info "Step 4: Creating App Service Plan..."
if az appservice plan show --resource-group "$RESOURCE_GROUP" --name "$APP_SERVICE_PLAN" &>/dev/null; then
    log_warn "App Service plan already exists: $APP_SERVICE_PLAN"
else
    az appservice plan create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$APP_SERVICE_PLAN" \
        --sku B2 \
        --is-linux \
        --output none
    log_success "App Service plan created: $APP_SERVICE_PLAN"
fi

# ---- Step 5: Create App Service ----
log_info "Step 5: Creating App Service..."
if az webapp show --resource-group "$RESOURCE_GROUP" --name "$APP_SERVICE" &>/dev/null; then
    log_warn "App Service already exists: $APP_SERVICE"
else
    az webapp create \
        --resource-group "$RESOURCE_GROUP" \
        --plan "$APP_SERVICE_PLAN" \
        --name "$APP_SERVICE" \
        --output none
    log_success "App Service created: $APP_SERVICE"
fi

# ---- Step 6: Build Docker Image ----
log_info "Step 6: Building Docker image..."
docker build \
    --build-arg VITE_APP_BASE_PATH='' \
    -t "$ACR_NAME.azurecr.io/$APP_BASE_NAME:latest" \
    -t "$ACR_NAME.azurecr.io/$APP_BASE_NAME:$ENVIRONMENT" \
    -f Dockerfile \
    .

if [ $? -eq 0 ]; then
    log_success "Docker image built successfully"
else
    log_error "Docker build failed"
    exit 1
fi

# ---- Step 7: Login to ACR ----
log_info "Step 7: Authenticating with Container Registry..."
az acr login --name "$ACR_NAME" --output none
log_success "Authenticated with ACR"

# ---- Step 8: Push Image to ACR ----
log_info "Step 8: Pushing Docker image to Container Registry..."
docker push "$ACR_NAME.azurecr.io/$APP_BASE_NAME:latest"
docker push "$ACR_NAME.azurecr.io/$APP_BASE_NAME:$ENVIRONMENT"
log_success "Image pushed to ACR"

# ---- Step 9: Get Azure Credentials ----
log_info "Step 9: Retrieving Azure credentials..."
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query "username" -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)
REDIS_HOST=$(az redis show --resource-group "$RESOURCE_GROUP" --name "$REDIS_NAME" --query "hostName" -o tsv)
REDIS_PASSWORD=$(az redis list-keys --resource-group "$RESOURCE_GROUP" --name "$REDIS_NAME" --query "primaryKey" -o tsv)
log_success "Credentials retrieved"

# ---- Step 10: Configure Container ----
log_info "Step 10: Configuring container settings..."
az webapp config container set \
    --name "$APP_SERVICE" \
    --resource-group "$RESOURCE_GROUP" \
    --docker-custom-image-name "$ACR_NAME.azurecr.io/$APP_BASE_NAME:latest" \
    --docker-registry-server-url "https://$ACR_NAME.azurecr.io" \
    --docker-registry-server-user "$ACR_USERNAME" \
    --docker-registry-server-password "$ACR_PASSWORD" \
    --output none
log_success "Container configured"

# ---- Step 11: Set Environment Variables ----
log_info "Step 11: Configuring environment variables..."
az webapp config appsettings set \
    --name "$APP_SERVICE" \
    --resource-group "$RESOURCE_GROUP" \
    --settings \
        REDIS_HOST="$REDIS_HOST" \
        REDIS_PORT="6380" \
        REDIS_PASSWORD="$REDIS_PASSWORD" \
        REDIS_SSL="true" \
        SYNCFUSION_LICENSE_KEY="$LICENSE_KEY" \
        BACKEND_URL="https://$APP_SERVICE.azurewebsites.net/" \
        WEBSITES_PORT="5000" \
        WEBSITES_ENABLE_APP_SERVICE_STORAGE="false" \
    --output none
log_success "Environment variables configured"

# ---- Step 12: Enable Logging ----
log_info "Step 12: Enabling diagnostic logging..."
az webapp log config \
    --name "$APP_SERVICE" \
    --resource-group "$RESOURCE_GROUP" \
    --docker-container-logging filesystem \
    --output none
log_success "Logging enabled"

# ---- Summary ----
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                   Deployment Complete!                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Application Details:"
APP_URL="https://$APP_SERVICE.azurewebsites.net"
echo "  📱 URL:            $APP_URL"
echo "  🔒 HTTPS:          Enabled"
echo "  📊 Resource Group:  $RESOURCE_GROUP"
echo "  🗄️ Redis Cache:    $REDIS_NAME.redis.cache.windows.net:6380"
echo ""

echo "Next Steps:"
echo "  1. View logs:       az webapp log tail --name $APP_SERVICE --resource-group $RESOURCE_GROUP"
echo "  2. Open browser:    $APP_URL"
echo "  3. Configure CORS:  Update CORS settings if needed"
echo "  4. Setup DNS:       Add custom domain if needed"
echo ""

echo "Useful Commands:"
echo "  View settings:      az webapp config appsettings list --name $APP_SERVICE --resource-group $RESOURCE_GROUP"
echo "  Update settings:    az webapp config appsettings set --name $APP_SERVICE --resource-group $RESOURCE_GROUP --settings KEY=VALUE"
echo "  View logs:          az webapp log tail --name $APP_SERVICE --resource-group $RESOURCE_GROUP --follow"
echo "  Restart app:        az webapp restart --name $APP_SERVICE --resource-group $RESOURCE_GROUP"
echo "  Delete resources:   az group delete --name $RESOURCE_GROUP"
echo ""

log_success "Deployment script completed successfully!"
