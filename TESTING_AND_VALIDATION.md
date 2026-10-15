# Testing and Validation Guide

Comprehensive testing procedures for local development and production deployment.

---

## Table of Contents

1. [Local Development Testing](#local-development-testing)
2. [Docker Image Validation](#docker-image-validation)
3. [Azure Deployment Validation](#azure-deployment-validation)
4. [End-to-End Testing](#end-to-end-testing)
5. [Performance Testing](#performance-testing)
6. [Troubleshooting](#troubleshooting)

---

## Local Development Testing

### 1.1 Prerequisites

```bash
# Verify Docker is running
docker ps

# Verify Docker Compose is available
docker-compose --version

# Verify Node.js (for frontend dev)
node --version
npm --version

# Verify Python (optional, for backend debugging)
python3 --version
```

### 1.2 Setup Local Environment

```bash
# Clone repository (if not already done)
git clone <repository-url>
cd Spreadsheet-Version-History

# Create environment file
cp .env.example .env

# Verify .env has correct values
cat .env
```

### 1.3 Start Local Services

```bash
# Start all services in background
docker-compose up -d

# Verify services are running
docker ps

# Expected output:
# - spreadsheet-redis (healthy)
# - spreadsheet-app (healthy)

# View startup logs
docker-compose logs -f app
```

### 1.4 Verify Services

```bash
# Check Redis connection
docker-compose exec redis redis-cli ping
# Expected: PONG

# Check Flask API endpoint
curl http://localhost:5000/api/DocumentEditor/Process
# Expected: 200 response (may be empty or error, but endpoint should exist)

# Check frontend load
curl http://localhost:5000/ | head -20
# Expected: HTML content with Spreadsheet app

# Check service health
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### 1.5 Test Frontend

```bash
# Open browser
open http://localhost:5000/
# or
xdg-open http://localhost:5000/
# or
start http://localhost:5000/

# In browser DevTools (F12):
# 1. Check Console for errors
# 2. Check Network tab for failed requests
# 3. Verify backend URL matches BACKEND_URL env var
```

### 1.6 Test Collaboration Features

```bash
# Open two browser windows/tabs at http://localhost:5000/?id=test-room
# 1. Make edits in first window
# 2. Verify changes appear in second window (requires Redis)

# Test WebSocket connection
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:5000/api/CollaborativeEditing/
# Expected: 101 Switching Protocols (or similar)
```

### 1.7 View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app
docker-compose logs -f redis

# Filter by time
docker-compose logs -f --since 10m app

# Last N lines
docker-compose logs --tail 50 app
```

### 1.8 Stop Services

```bash
# Stop without removing
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop, remove, and delete volumes
docker-compose down -v
```

---

## Docker Image Validation

### 2.1 Build Docker Image

```bash
# Build locally
docker build -t spreadsheet-app:latest .

# Expected output:
# - Multiple build stages complete
# - "Successfully built ..." message
# - No errors or warnings

# Verify image exists
docker images | grep spreadsheet-app

# Check image size
docker images --format "table {{.Repository}}\t{{.Size}}" | grep spreadsheet-app
# Expected: ~1.2 GB (includes .NET, graphics libs, Python, Node)
```

### 2.2 Test Image Locally

```bash
# Run container from image
docker run -d \
  -p 5000:5000 \
  -e REDIS_HOST=host.docker.internal \
  -e REDIS_PORT=6379 \
  -e REDIS_PASSWORD= \
  -e REDIS_SSL=false \
  --name test-app \
  spreadsheet-app:latest

# Wait for startup
sleep 10

# Check logs
docker logs test-app

# Test endpoint
curl http://localhost:5000/api/DocumentEditor/Process

# Stop container
docker stop test-app
docker rm test-app
```

### 2.3 Scan Image for Vulnerabilities

```bash
# Install trivy (if available)
trivy image spreadsheet-app:latest

# Or use docker scan
docker scan spreadsheet-app:latest

# Review HIGH and CRITICAL vulnerabilities
# Medium/Low can usually be ignored for internal apps
```

### 2.4 Verify Image Layers

```bash
# Show layers and sizes
docker history spreadsheet-app:latest

# Check for large unnecessary layers
# If frontend or build stages are unusually large:
# - Remove node_modules from final image ✓ (multi-stage does this)
# - Ensure --no-cache-dir flag on pip ✓ (Dockerfile includes)
# - Clear apt cache ✓ (Dockerfile includes)
```

---

## Azure Deployment Validation

### 3.1 Pre-Deployment Checklist

```bash
# ✓ Verify credentials are not in code
grep -r "redis263327.redis.cache.windows.net" . --exclude-dir=.git
# Should return: nothing

grep -r "Your.*Key" . --exclude-dir=.git
# Should return: only examples in .env.example or documentation

# ✓ Verify .dockerignore is properly configured
cat .dockerignore | grep -E "\.git|\.env|node_modules"

# ✓ Verify no large files in Docker context
du -sh . --exclude=.git --exclude=node_modules
```

### 3.2 Deploy Using Script

```bash
# Make script executable
chmod +x scripts/azure-deploy.sh

# Deploy to development environment
./scripts/azure-deploy.sh dev "YOUR_SYNCFUSION_LICENSE_KEY"

# Deploy to production environment
./scripts/azure-deploy.sh prod "YOUR_SYNCFUSION_LICENSE_KEY" "myapp"

# Script will:
# - Create resource group
# - Create container registry
# - Create Redis cache
# - Create App Service plan
# - Create App Service
# - Build and push Docker image
# - Configure all settings
# - Output app URL
```

### 3.3 Manual Deployment (Step-by-Step)

```bash
# 1. Set variables
RG="rg-spreadsheet-prod"
APP="spreadsheet-app"
LOCATION="eastus"

# 2. Create resource group
az group create --name $RG --location $LOCATION

# 3. Create container registry
az acr create --resource-group $RG --name ${APP//-/}acr --sku Basic

# 4. Login to ACR
az acr login --name ${APP//-/}acr

# 5. Build and push image
docker build -t ${APP//-/}acr.azurecr.io/$APP:latest .
docker push ${APP//-/}acr.azurecr.io/$APP:latest

# 6. Create Redis cache
az redis create --resource-group $RG --name $APP-redis --location $LOCATION --sku Basic --vm-size c0

# 7. Create App Service Plan
az appservice plan create --resource-group $RG --name $APP-plan --sku B2 --is-linux

# 8. Create App Service
az webapp create --resource-group $RG --plan $APP-plan --name $APP

# 9. Configure container
ACR_NAME="${APP//-/}acr"
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query "username" -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)

az webapp config container set \
  --name $APP --resource-group $RG \
  --docker-custom-image-name "$ACR_NAME.azurecr.io/$APP:latest" \
  --docker-registry-server-url "https://$ACR_NAME.azurecr.io" \
  --docker-registry-server-user "$ACR_USERNAME" \
  --docker-registry-server-password "$ACR_PASSWORD"

# 10. Set environment variables
REDIS_HOST=$(az redis show --resource-group $RG --name $APP-redis --query "hostName" -o tsv)
REDIS_PASSWORD=$(az redis list-keys --resource-group $RG --name $APP-redis --query "primaryKey" -o tsv)

az webapp config appsettings set \
  --name $APP --resource-group $RG --settings \
    REDIS_HOST="$REDIS_HOST" \
    REDIS_PORT="6380" \
    REDIS_PASSWORD="$REDIS_PASSWORD" \
    REDIS_SSL="true" \
    SYNCFUSION_LICENSE_KEY="YOUR_KEY" \
    BACKEND_URL="https://$APP.azurewebsites.net/"
```

### 3.4 Verify Deployment

```bash
# Check app status
az webapp show --name $APP --resource-group $RG --query "state" -o tsv
# Expected: Running

# Get app URL
APP_URL="https://$(az webapp show --name $APP --resource-group $RG --query 'defaultHostName' -o tsv)"
echo "App URL: $APP_URL"

# Test endpoint
curl "$APP_URL/api/DocumentEditor/Process"
curl -i "$APP_URL/"

# View logs
az webapp log tail --name $APP --resource-group $RG --follow

# Check container status
az webapp config container show --name $APP --resource-group $RG
```

---

## End-to-End Testing

### 4.1 Functional Testing

#### Test 1: Frontend Load

```bash
# Navigate to app URL
# Expected:
# ✓ Page loads without errors
# ✓ Spreadsheet grid is visible
# ✓ No console errors (F12 → Console)
# ✓ Backend URL is correct (F12 → Network, check API calls)
```

#### Test 2: API Endpoints

```bash
# Check main API endpoint
curl -X POST $APP_URL/api/DocumentEditor/Process \
  -H "Content-Type: application/json" \
  -d '{}'
# Expected: 200 or 400 (endpoint exists)

# Check collaboration endpoint
curl $APP_URL/api/CollaborativeEditing/ImportFile
# Expected: 404 or error (endpoint exists)

# Check health endpoint (if configured)
curl $APP_URL/health
```

#### Test 3: Collaboration (Multi-User)

```bash
# User 1: Open app
open "$APP_URL?id=test-room"

# User 2: Open same URL in another tab/window
# Make changes in User 1 → should appear in User 2
# Make changes in User 2 → should appear in User 1
```

#### Test 4: Redis Connectivity

```bash
# Check Redis connection from App Service logs
az webapp log tail --name $APP --resource-group $RG | grep -i redis

# Expected: "[Redis] Connected to ..."
# Or if fails: "[REDIS] Connection failed: ..."
```

### 4.2 Performance Testing

#### Load Test (Simple)

```bash
# Install Apache Bench
# macOS: brew install httpd
# Ubuntu: sudo apt-get install apache2-utils
# Windows: Use WSL or download ab.exe

# Test homepage
ab -n 100 -c 10 "$APP_URL/"

# Test API
ab -n 100 -c 10 "$APP_URL/api/DocumentEditor/Process"

# Results to check:
# - Requests per second (RPS)
# - Failed requests (should be 0)
# - Response time (should be < 1000ms for homepage)
```

#### Stress Test

```bash
# Longer test with more concurrent users
ab -n 1000 -c 50 "$APP_URL/"

# Monitor Azure Portal during test:
# - CPU %
# - Memory %
# - Response Time
# - HTTP 5xx Errors
```

---

## Troubleshooting

### Common Issues

#### Issue: Container fails to start

**Logs:**
```
docker logs spreadsheet-app
# Output shows: "ERROR: ..." or "ModuleNotFoundError: ..."
```

**Solutions:**

```bash
# 1. Check if image built successfully
docker build -t test:latest .

# 2. Review Dockerfile for errors
cat Dockerfile | grep -A 5 -B 5 "ERROR"

# 3. Check base image availability
docker pull mcr.microsoft.com/dotnet/aspnet:10.0

# 4. Verify all files are copied
docker run -it test:latest ls -la /app
```

#### Issue: Redis connection fails

**Error in logs:**
```
[REDIS] Connection failed: ConnectionError: ...
```

**Solutions:**

```bash
# 1. Check if Redis is running (local)
docker-compose ps redis

# 2. Verify Redis credentials
az redis list-keys --resource-group $RG --name $APP-redis

# 3. Test connection manually
redis-cli -h $REDIS_HOST -p 6380 -a $REDIS_PASSWORD ping

# 4. Check firewall rules (Azure)
az redis firewall-rules list --resource-group $RG --name $APP-redis
```

#### Issue: Frontend shows blank page

**Browser Console Shows:**
```
Uncaught ReferenceError: __BACKEND_URL__ is not defined
```

**Solutions:**

```bash
# 1. Check BACKEND_URL environment variable
az webapp config appsettings show --name $APP --resource-group $RG | grep BACKEND_URL

# 2. Verify frontend HTML has config injected
curl $APP_URL/ | grep -i "BACKEND_URL"

# 3. Check network requests in browser DevTools
# - Look for failed API calls
# - Verify URLs are correct
# - Check CORS headers
```

#### Issue: License key not recognized

**Error in logs:**
```
[License] Warning: No Syncfusion license key found
```

**Solutions:**

```bash
# 1. Verify license key is set
az webapp config appsettings show --name $APP --resource-group $RG | grep LICENSE

# 2. Verify license key format
# Should be: long alphanumeric string (no "YOUR_" prefix)

# 3. Restart app after setting license
az webapp restart --name $APP --resource-group $RG

# 4. Verify in logs
az webapp log tail --name $APP --resource-group $RG | grep -i license
```

#### Issue: Port 5000 already in use (local)

**Error:**
```
Address already in use
```

**Solutions:**

```bash
# 1. Find process using port 5000
lsof -i :5000
# or (Windows): netstat -ano | findstr :5000

# 2. Kill process (if needed)
kill -9 <PID>
# or (Windows): taskkill /PID <PID> /F

# 3. Or use different port in docker-compose
# Edit docker-compose.yml:
# ports:
#   - "5001:5000"
```

### Debug Commands

```bash
# Docker Compose debugging
docker-compose exec app bash
python3 -c "import redis; print(redis.__version__)"
python3 -c "import clr; print('CLR loaded')"

# Azure debugging
az webapp log tail --name $APP --resource-group $RG --follow
az webapp show --name $APP --resource-group $RG --query "properties"

# Redis debugging
redis-cli -h $REDIS_HOST -p 6380 -a $REDIS_PASSWORD
> INFO
> KEYS *
> GET key_name

# Image debugging
docker run -it spreadsheet-app:latest bash
# Inside container:
python3 --version
npm --version
dotnet --version
```

---

## Validation Checklist

### Pre-Production

- [ ] No hardcoded credentials in code/git
- [ ] Docker image builds without warnings
- [ ] All dependencies installed (npm, pip)
- [ ] Frontend builds with no errors
- [ ] .NET wrapper compiles successfully
- [ ] Healthcheck passes
- [ ] Local docker-compose deployment works
- [ ] All environment variables documented
- [ ] License key is valid
- [ ] Redis connection works

### Post-Deployment

- [ ] App Service is running
- [ ] Frontend loads without errors
- [ ] API endpoints respond
- [ ] Redis connection successful
- [ ] License key registered
- [ ] Logs show no errors
- [ ] CPU/Memory usage reasonable
- [ ] HTTPS redirects work
- [ ] Custom domain (if configured)
- [ ] Backups configured

### Security

- [ ] No credentials in environment variables (use Key Vault)
- [ ] HTTPS only enforced
- [ ] CORS properly configured
- [ ] Network security groups (NSG) configured
- [ ] Service endpoints enabled
- [ ] Azure Defender enabled
- [ ] Audit logging enabled
- [ ] Secrets rotated regularly

---

## Performance Baseline

These are expected performance metrics for a B2 App Service plan with default configuration:

| Metric | Value | Notes |
|--------|-------|-------|
| Page Load Time | < 2 seconds | Depends on network |
| API Response | < 500ms | Typical operation |
| Concurrent Users | 10-20 | Per B2 instance |
| Requests/sec | 50-100 | Gunicorn with 1 worker |
| CPU Usage | 20-40% | Idle to light usage |
| Memory Usage | 500-800MB | Container typically uses |
| Redis Latency | < 10ms | From App Service to Redis |

---

## References

- [Azure App Service Diagnostics](https://learn.microsoft.com/en-us/azure/app-service/overview-diagnostics)
- [Docker CLI Reference](https://docs.docker.com/engine/reference/commandline/cli/)
- [Redis CLI Reference](https://redis.io/docs/manual/cli/)
- [Azure CLI Reference](https://learn.microsoft.com/en-us/cli/azure/reference-index)
- [Apache Bench Documentation](https://httpd.apache.org/docs/2.4/programs/ab.html)
