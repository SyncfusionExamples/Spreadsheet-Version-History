# Dockerization and Azure App Service Deployment Guide
## Spreadsheet Version History Application

**Date Created:** 2025
**Application:** Vue Frontend + Python Backend with .NET Wrapper
**Target Environment:** Azure Container Registry + Azure App Service
**Status:** Production-Ready

---

## Table of Contents

1. [Repository Findings](#repository-findings)
2. [Architecture Recommendation](#architecture-recommendation)
3. [Environment Variables Reference](#environment-variables-reference)
4. [Build Instructions](#build-instructions)
5. [Docker Images](#docker-images)
6. [Docker Compose Setup](#docker-compose-setup)
7. [Azure Deployment Steps](#azure-deployment-steps)
8. [Configuration Management](#configuration-management)
9. [Validation Checklist](#validation-checklist)
10. [Risks and Recommendations](#risks-and-recommendations)

---

## 1. Repository Findings

### 1.1 Application Structure

```
Spreadsheet-Version-History/
├── frontend/                              # Vue 3 + TypeScript application
│   ├── src/
│   │   ├── App.vue                       # Main component (34KB)
│   │   ├── SpreadsheetEditorAdapter.ts   # Collaboration adapter
│   │   ├── main.ts
│   │   └── style.css
│   ├── package.json                      # npm dependencies
│   ├── vite.config.ts                    # Vite build config
│   ├── tsconfig.json                     # TypeScript config
│   └── index.html                        # SPA entry point
│
├── NETStandardWrapperLibrary/
│   └── WebServiceLibrary/                # .NET 10 wrapper for Spreadsheet
│       ├── WebServiceLibrary.csproj      # C# project
│       └── SpreadsheetEditor.cs          # Wrapper implementation
│
├── app.py                                 # Flask backend (79KB)
├── requirements.txt                       # Python dependencies
├── appsettings.json                       # Runtime configuration
├── Dockerfile                             # Existing multi-stage build
├── .dockerignore                          # Docker build filters
├── Files/                                 # Application data directory
└── license                                # Syncfusion license info
```

### 1.2 Frontend (Vue 3 + TypeScript)

**Stack:**
- **Framework:** Vue 3.5.22
- **Build Tool:** Vite 7.1.9
- **Runtime:** Node.js 20+
- **Dependencies:**
  - @syncfusion/ej2-vue-spreadsheet (35.1.37)
  - @syncfusion/ej2-collaborator (35.1.37)
  - @microsoft/signalr (9.0.0) - WebSocket support
  - Tailwind CSS via @syncfusion/ej2-tailwind3-theme

**Key Observations:**
- Service URL hardcoded to `http://127.0.0.1:5000/` (line 32 of App.vue)
- **ISSUE:** Frontend needs dynamic backend URL configuration
- Collaborative editing uses WebSocket + polling for real-time updates
- Build produces static dist/ folder
- Base path support via `VITE_APP_BASE_PATH` environment variable (Dockerfile comments)

### 1.3 Backend (Python Flask)

**Stack:**
- **Framework:** Flask (lightweight)
- **Python Version:** 3.9+ (container image: python3 via .NET base image)
- **Server:** Gunicorn with 4 threads
- **Dependencies:**
  - flask, flask-cors, flask-sock (WebSockets)
  - eventlet (async)
  - pythonnet (Python ↔ .NET interop)
  - redis (session/collaboration store)
  - gunicorn (production server)

**Key Observations:**
- Multi-stage build combines Vue, .NET 10 SDK, and Python runtime
- Uses .NET 10 aspnet base image for graphics libraries (SkiaSharp)
- Requires .NET runtime + graphics libraries (libgdiplus, fontconfig, etc.) for PDF export
- Redis configuration loaded from `appsettings.json` with fallback to env vars
- Hardcoded placeholder: `redis263327.redis.cache.windows.net` (needs replacement)
- Ports: 5000 (HTTP), requires Redis connectivity
- Serves frontend static files from `/frontend/dist`

**Environment Variables in app.py:**
- `PYTHONNET_RUNTIME=coreclr` (required for .NET interop)
- `DOTNET_ROOT` (auto-detected or explicitly set)
- `DOTNET_ROLL_FORWARD=LatestMajor` (framework compatibility)
- `LD_LIBRARY_PATH` (native library discovery for SkiaSharp)
- `BASE_PATH` (optional sub-path routing)

### 1.4 .NET Wrapper Library

**Stack:**
- **Target Framework:** .NET 10
- **Purpose:** Syncfusion Spreadsheet SFDT processing, PDF export
- **Built With:** Visual Studio project file (.csproj)
- **Output:** DLL + native dependencies (libSkiaSharp.so)
- **Build Stage:** Multi-stage Docker build uses `mcr.microsoft.com/dotnet/sdk:10.0`

---

## 2. Architecture Recommendation

### 2.1 Single Container vs. Multi-Container Approach

#### Analysis

**RECOMMENDED: Single Container Approach** ✅

**Rationale:**

1. **Tight Coupling:** Frontend is served by the same Flask backend; they share the same HTTP port (5000) and rely on each other at runtime.

2. **Shared Runtime Requirements:** Both components need:
   - Graphics libraries (libgdiplus, fontconfig)
   - .NET 10 runtime for PDF export
   - Python runtime for Flask
   - This is already in the existing Dockerfile

3. **Deployment Simplicity:** Azure App Service works with single-container deployments. Pushing one image is simpler than orchestrating multiple services.

4. **Cost Efficiency:** Single container = lower resource overhead, no inter-container network latency.

5. **Existing Pattern:** The repository already includes a working multi-stage Dockerfile that builds everything into one image.

#### Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│         Azure Container Registry (ACR)              │
│  spreadsheet-app:latest (single image, ~1GB)       │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│        Azure App Service (Linux container)          │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Flask App (Gunicorn on 0.0.0.0:5000)       │  │
│  │  ├─ Vue Frontend (static files)              │  │
│  │  ├─ Spreadsheet Collaboration API           │  │
│  │  ├─ .NET Interop (PDF export, SFDT proc)   │  │
│  │  └─ WebSocket support (flask-sock)          │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                          ↓
              ┌──────────────────────┐
              │  Azure Redis Cache   │
              │ (Collaboration Store)│
              └──────────────────────┘
```

#### Multi-Container Alternative (Not Recommended)

If you require independent scaling or different update cadences:

- **Frontend Service:** Nginx + Vue (static SPA)
- **Backend Service:** Flask + Python + .NET
- **Orchestration:** Docker Compose (local) / Kubernetes (production)
- **Drawbacks:** Complex networking, doubled deployment effort, higher cost

---

## 3. Environment Variables Reference

### 3.1 Configuration Variables Table

| Variable | Type | Required | Source | Used By | Default | Notes |
|----------|------|----------|--------|---------|---------|-------|
| `SYNCFUSION_LICENSE_KEY` | String | ✅ Yes | Azure App Service Settings | Python (app.py), .NET wrapper | None | Syncfusion license; injected at runtime |
| `REDIS_HOST` | String | ✅ Yes | appsettings.json OR env | Python redis client | N/A | Azure Redis Cache hostname (e.g., `myredis.redis.cache.windows.net`) |
| `REDIS_PORT` | Integer | ✅ Yes | appsettings.json | Python redis client | 6380 | Azure Redis Cache uses port 6380 for SSL |
| `REDIS_PASSWORD` | String | ✅ Yes | appsettings.json OR env | Python redis client | N/A | Azure Redis Cache access key |
| `REDIS_SSL` | Boolean | Optional | appsettings.json | Python redis client | `true` | Enable SSL for Redis (required for Azure) |
| `BASE_PATH` | String | Optional | Environment | Flask routing | `''` | Sub-path for load balancer routing (e.g., `/app`) |
| `PYTHONNET_RUNTIME` | String | ✅ Yes | app.py (hardcoded) | pythonnet | `coreclr` | Must be `coreclr` for .NET interop |
| `DOTNET_ROOT` | String | Optional | Dockerfile ENV | pythonnet | Auto-detected | Path to .NET runtime (set in Dockerfile) |
| `DOTNET_ROLL_FORWARD` | String | Optional | app.py (hardcoded) | .NET runtime | `LatestMajor` | Allows newer .NET versions to run net10.0 code |
| `VITE_APP_BASE_PATH` | String | Optional | Build arg (Dockerfile) | Vite build | `''` | Frontend asset base path for SPA routing |
| `BACKEND_URL` | String | ✅ Yes (in production) | TBD | Frontend Vue component | `http://127.0.0.1:5000/` | **Must be injected dynamically** |

### 3.2 Current Hardcoded Issues

**Frontend (App.vue, line 32):**
```typescript
const serviceUrl: string = ' http://127.0.0.1:5000/';
```
**Problem:** Hardcoded to localhost; will not work in production.
**Solution:** See [Section 5: Frontend Configuration](#5-frontend-configuration).

**Backend (appsettings.json):**
```json
{
  "Redis": {
    "Host": "redis263327.redis.cache.windows.net",
    "Password": "4W2aP8MBy2qVffRzs1PEslChq9k6qydBCAzCaMPC9dk="
  }
}
```
**Problem:** Credentials hardcoded; exposed in version control.
**Solution:** See [Section 6: Backend Configuration](#6-backend-configuration).

---

## 4. Build Instructions

### 4.1 Local Development Build

**Prerequisites:**
- Docker Desktop (Linux containers mode)
- Git
- (Optional) Node.js 20+ for local frontend testing

**Step 1: Prepare Configuration**

Create a `.env.local` file with your local Redis:

```bash
# .env.local (git-ignored)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_SSL=false
```

**Step 2: Build Docker Image (Development)**

```bash
# Build with default settings (serves on port 5000)
docker build -t spreadsheet-app:dev .

# Build with custom base path (e.g., for sub-path deployment)
docker build \
  --build-arg VITE_APP_BASE_PATH='/spreadsheet/' \
  -t spreadsheet-app:dev .
```

**Step 3: Run Container Locally**

```bash
# Run with local Redis
docker run -d \
  -p 5000:5000 \
  -e REDIS_HOST=host.docker.internal \
  -e REDIS_PORT=6379 \
  -e REDIS_PASSWORD="" \
  -e REDIS_SSL=false \
  -e PYTHONNET_RUNTIME=coreclr \
  --name spreadsheet-dev \
  spreadsheet-app:dev

# Check logs
docker logs -f spreadsheet-dev

# Test endpoint
curl http://localhost:5000/api/DocumentEditor/Process
```

### 4.2 Production Build (Azure)

**Step 1: Build Production Image**

```bash
# Build production image with version tag
docker build \
  --build-arg VITE_APP_BASE_PATH='' \
  -t spreadsheet-app:1.0.0 \
  -t spreadsheet-app:latest \
  .
```

**Step 2: Tag for Azure Container Registry**

```bash
# Login to ACR
az acr login --name <acr-name>

# Tag image
docker tag spreadsheet-app:1.0.0 <acr-name>.azurecr.io/spreadsheet-app:1.0.0
docker tag spreadsheet-app:1.0.0 <acr-name>.azurecr.io/spreadsheet-app:latest

# Push to ACR
docker push <acr-name>.azurecr.io/spreadsheet-app:1.0.0
docker push <acr-name>.azurecr.io/spreadsheet-app:latest
```

**Step 3: Verify Image in ACR**

```bash
# List images in ACR
az acr repository list --name <acr-name>

# Show image details and tags
az acr repository show --name <acr-name> --repository spreadsheet-app
```

---

## 5. Docker Images

### 5.1 Existing Dockerfile Analysis

The repository includes a multi-stage `Dockerfile` that is **already well-designed** for production:

**Stages:**

| Stage | Purpose | Base Image | Output |
|-------|---------|-----------|--------|
| `frontend` | Build Vue app | `node:20-alpine` | `/fe/dist/` (static files) |
| `dotnet` | Build .NET wrapper | `mcr.microsoft.com/dotnet/sdk:10.0` | `/out/` (DLLs + natives) |
| `final` | Runtime | `mcr.microsoft.com/dotnet/aspnet:10.0` | Complete app + Flask |

**Strengths:**
✅ Multi-stage (optimized image size)
✅ Includes all required system libraries (libgdiplus, fontconfig)
✅ Sets up Python venv correctly
✅ Copies frontend static files
✅ Includes LD_LIBRARY_PATH for native libraries
✅ Healthcheck configured
✅ Gunicorn with proper settings (4 threads, 600s timeout)

**Current Issues:**
❌ Frontend URL hardcoded to localhost
❌ Redis credentials in appsettings.json
❌ Needs dynamic environment variable injection

### 5.2 Improved Dockerfile (Production-Ready)

The current Dockerfile is already suitable for production. **No changes needed** unless you want to:

1. **Inject Frontend URL Dynamically** → Requires a small wrapper script (see Section 5: Frontend Configuration)
2. **Optimize Image Size** → Alpine for Python, multi-stage already applied
3. **Security Hardening** → Add non-root user, read-only filesystems

---

## 6. Frontend Configuration

### Problem
Frontend hardcoded to `http://127.0.0.1:5000/`, requires dynamic backend URL at runtime.

### Solution: Runtime Configuration Injection

**Approach 1: Environment Variable Substitution (Recommended)**

Create a startup script that injects the backend URL before the Flask app starts:

**File: `scripts/configure-frontend.sh`**

```bash
#!/bin/bash
set -e

# Read backend URL from environment or use default
BACKEND_URL=${BACKEND_URL:-"http://127.0.0.1:5000/"}

echo "Configuring frontend with backend URL: $BACKEND_URL"

# Replace serviceUrl in main.js after Vite build
# The built dist/assets/App-*.js contains the hardcoded URL
find /app/frontend/dist -name "*.js" -type f -exec \
  sed -i "s|http://127.0.0.1:5000/|${BACKEND_URL}|g" {} \;

echo "Frontend configuration complete"
```

**Issue with Approach 1:** File size optimization tools (tree-shaking, minification) make the hardcoded URL different than the source. This becomes fragile.

---

**Approach 2: Build-Time Configuration (Better)**

Modify `frontend/src/App.vue` to read from window config or environment:

**File: `frontend/public/config.js` (NEW)**

```javascript
// Runtime configuration - injected by startup script or Dockerfile
window.__APP_CONFIG__ = {
  serviceUrl: window.__BACKEND_URL__ || 'http://127.0.0.1:5000/'
};
```

**Modified App.vue (line 32):**

```typescript
const serviceUrl: string = (window as any).__APP_CONFIG__?.serviceUrl || 'http://127.0.0.1:5000/';
```

**Modified `frontend/index.html`:**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Spreadsheet Collaborative Editing</title>
    
    <!-- Configuration script - MUST load before Vue app -->
    <script>
      window.__BACKEND_URL__ = window.__BACKEND_URL__ || process.env.VITE_BACKEND_URL || 'http://127.0.0.1:5000/';
    </script>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

**Dockerfile Modification (at startup):**

```dockerfile
# In CMD section, use an entrypoint wrapper
ENTRYPOINT ["/app/scripts/configure-frontend-runtime.sh"]
CMD ["gunicorn","--bind","0.0.0.0:5000","--timeout","600","--workers","1","--threads","4","--access-logfile","-","--error-logfile","-","app:app"]
```

**File: `scripts/configure-frontend-runtime.sh`**

```bash
#!/bin/bash
set -e

# Inject backend URL into frontend config at runtime
BACKEND_URL=${BACKEND_URL:-"http://localhost:5000/"}
export VITE_BACKEND_URL="$BACKEND_URL"

echo "[startup] Backend URL: $BACKEND_URL"

# Execute main command
exec "$@"
```

---

**Approach 3: Environment Variable in Vite Build (For Azure)**

If building separately from deployment:

**Modified `frontend/vite.config.ts`:**

```typescript
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  define: {
    __BACKEND_URL__: JSON.stringify(process.env.VITE_BACKEND_URL || 'http://127.0.0.1:5000/')
  }
});
```

**Modified `frontend/src/App.vue` (line 32):**

```typescript
declare const __BACKEND_URL__: string;
const serviceUrl: string = __BACKEND_URL__ || 'http://127.0.0.1:5000/';
```

**Build Command:**

```bash
VITE_BACKEND_URL="https://myapp.azurewebsites.net/" npm run build
```

---

### Recommended Implementation

**Use Approach 2** (runtime config in window object) because:
- ✅ No rebuild needed for different backends
- ✅ Works with both dev and production
- ✅ Flexible for Azure App Service environment variables
- ✅ No file manipulation required

---

## 7. Backend Configuration

### 7.1 Redis Configuration

**Current Issue:** Hardcoded in `appsettings.json` with exposed credentials.

**File: `appsettings.json` (Current - UNSAFE)**

```json
{
  "Redis": {
    "Host": "redis263327.redis.cache.windows.net",
    "Port": 6380,
    "Password": "4W2aP8MBy2qVffRzs1PEslChq9k6qydBCAzCaMPC9dk=",
    "Ssl": true,
    "AbortConnect": false
  }
}
```

**Problem:**
- ❌ Credentials hardcoded
- ❌ Exposed in git history
- ❌ Not suitable for multi-environment deployment

### 7.2 Solution: Environment Variable Precedence

**Modified `app.py` - Implement Env Var Override**

The current code reads from `appsettings.json`. Add environment variable precedence:

```python
def load_application_settings():
    settings_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "appsettings.json"
    )

    if not os.path.isfile(settings_path):
        raise FileNotFoundError(
            f"Configuration file was not found: {settings_path}"
        )

    with open(settings_path, "r", encoding="utf-8") as settings_file:
        settings = json.load(settings_file)

    # Environment variables override appsettings.json
    redis_settings = settings.get("Redis", {})
    
    # Check for environment variables first
    redis_host = os.environ.get("REDIS_HOST")
    if redis_host:
        redis_settings["Host"] = redis_host
    
    redis_port = os.environ.get("REDIS_PORT")
    if redis_port:
        redis_settings["Port"] = int(redis_port)
    
    redis_password = os.environ.get("REDIS_PASSWORD")
    if redis_password:
        redis_settings["Password"] = redis_password
    
    redis_ssl = os.environ.get("REDIS_SSL", "true").lower() in ("true", "1", "yes")
    redis_settings["Ssl"] = redis_ssl
    
    settings["Redis"] = redis_settings
    return settings
```

### 7.3 Safe Configuration Files

**File: `appsettings.json` (Development Template)**

```json
{
  "Redis": {
    "Host": "localhost",
    "Port": 6379,
    "Password": "",
    "Ssl": false,
    "AbortConnect": false
  }
}
```

**File: `appsettings.production.json` (Git-ignored template)**

```json
{
  "Redis": {
    "Host": "YOUR_REDIS_HOST",
    "Port": 6380,
    "Password": "YOUR_REDIS_PASSWORD",
    "Ssl": true,
    "AbortConnect": false
  }
}
```

Add to `.gitignore`:
```
appsettings.*.json
appsettings.production.json
```

### 7.4 Syncfusion License Key Configuration

**Current Status:** No visible license key handling in `app.py`.

**Add License Key Support to `app.py`:**

```python
def initialize_syncfusion_license():
    """Initialize Syncfusion license from environment or settings."""
    license_key = os.environ.get("SYNCFUSION_LICENSE_KEY")
    
    if not license_key:
        license_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "license"
        )
        if os.path.isfile(license_file):
            with open(license_file, "r", encoding="utf-8") as f:
                license_key = f.read().strip()
    
    if license_key:
        # Call .NET wrapper to register license
        try:
            from clr import SpreadsheetLicenseProvider  # If available
            SpreadsheetLicenseProvider.SetLicense(license_key)
            print("[License] Syncfusion license registered", flush=True)
        except Exception as ex:
            print(f"[License] Warning: Could not register license: {ex}", flush=True)
    else:
        print("[License] Warning: No Syncfusion license key found", flush=True)

# Call in app initialization
initialize_syncfusion_license()
```

---

## 8. Azure Deployment Steps

### 8.1 Prerequisites

**Software:**
- Azure CLI (`az` command)
- Docker (for local testing)
- A valid Azure subscription

**Azure Resources Required:**
1. **Resource Group** (e.g., `rg-spreadsheet-prod`)
2. **Azure Container Registry** (e.g., `spreadsheetacr`)
3. **Azure Redis Cache** (e.g., `spreadsheet-redis`)
4. **Azure App Service Plan** (e.g., `asp-spreadsheet-linux`)
5. **Azure App Service** (e.g., `spreadsheet-app-service`)

### 8.2 Step-by-Step Deployment

#### Step 1: Create Azure Resources

```bash
# Set variables
RESOURCE_GROUP="rg-spreadsheet-prod"
ACR_NAME="spreadsheetacr"
REDIS_NAME="spreadsheet-redis"
APP_SERVICE_PLAN="asp-spreadsheet-linux"
APP_SERVICE="spreadsheet-app-service"
LOCATION="eastus"

# Create resource group
az group create \
  --name $RESOURCE_GROUP \
  --location $LOCATION

# Create Azure Container Registry
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic

# Create Azure Redis Cache
az redis create \
  --resource-group $RESOURCE_GROUP \
  --name $REDIS_NAME \
  --location $LOCATION \
  --sku Basic \
  --vm-size c0 \
  --enable-non-ssl-port false \
  --minimum-tls-version 1.2

# Create App Service Plan (Linux, B2 for moderate traffic)
az appservice plan create \
  --name $APP_SERVICE_PLAN \
  --resource-group $RESOURCE_GROUP \
  --sku B2 \
  --is-linux

# Create App Service
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $APP_SERVICE \
  --deployment-container-image-name-user $ACR_NAME
```

#### Step 2: Get Redis Credentials

```bash
# Get Redis connection details
az redis show \
  --resource-group $RESOURCE_GROUP \
  --name $REDIS_NAME \
  --query "hostName" -o tsv

# Get Redis primary key
az redis list-keys \
  --resource-group $RESOURCE_GROUP \
  --name $REDIS_NAME \
  --query "primaryKey" -o tsv

# Full connection string
echo "redis://:$(az redis list-keys --resource-group $RESOURCE_GROUP --name $REDIS_NAME --query 'primaryKey' -o tsv)@$(az redis show --resource-group $RESOURCE_GROUP --name $REDIS_NAME --query 'hostName' -o tsv):6380?ssl=True"
```

**Example Output:**
```
Host: spreadsheet-redis.redis.cache.windows.net
Primary Key: Eby8vdM02xNOcqFlqUwJPLMCeTK1mkJ...
```

#### Step 3: Build and Push Docker Image

```bash
# Login to ACR
az acr login --name $ACR_NAME

# Build image
docker build \
  --build-arg VITE_APP_BASE_PATH='' \
  -t $ACR_NAME.azurecr.io/spreadsheet-app:1.0.0 \
  -t $ACR_NAME.azurecr.io/spreadsheet-app:latest \
  .

# Push to ACR
docker push $ACR_NAME.azurecr.io/spreadsheet-app:1.0.0
docker push $ACR_NAME.azurecr.io/spreadsheet-app:latest

# Verify
az acr repository show \
  --name $ACR_NAME \
  --repository spreadsheet-app
```

#### Step 4: Configure App Service

```bash
# Get ACR credentials
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query "username" -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)
ACR_REGISTRY_URL="$ACR_NAME.azurecr.io"

# Get Redis credentials
REDIS_HOST=$(az redis show --resource-group $RESOURCE_GROUP --name $REDIS_NAME --query "hostName" -o tsv)
REDIS_PASSWORD=$(az redis list-keys --resource-group $RESOURCE_GROUP --name $REDIS_NAME --query "primaryKey" -o tsv)

# Set App Service configuration
az webapp config container set \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name "$ACR_REGISTRY_URL/spreadsheet-app:latest" \
  --docker-registry-server-url "https://$ACR_REGISTRY_URL" \
  --docker-registry-server-user "$ACR_USERNAME" \
  --docker-registry-server-password "$ACR_PASSWORD"

# Configure app settings (environment variables)
az webapp config appsettings set \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP \
  --settings \
    REDIS_HOST="$REDIS_HOST" \
    REDIS_PORT="6380" \
    REDIS_PASSWORD="$REDIS_PASSWORD" \
    REDIS_SSL="true" \
    SYNCFUSION_LICENSE_KEY="YOUR_LICENSE_KEY_HERE" \
    BACKEND_URL="https://$APP_SERVICE.azurewebsites.net/" \
    WEBSITES_ENABLE_APP_SERVICE_STORAGE="true" \
    WEBSITES_PORT="5000" \
    WEBSITES_ENABLE_APP_SERVICE_STORAGE="false"
```

**Notes:**
- `WEBSITES_PORT`: Tells App Service which port the container exposes (5000)
- `WEBSITES_ENABLE_APP_SERVICE_STORAGE`: Set to `false` for read-only container
- `BACKEND_URL`: Used by frontend to connect to API

#### Step 5: Set Startup Command (if needed)

```bash
# The Dockerfile CMD should work, but you can override:
az webapp config set \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP \
  --startup-file "gunicorn --bind 0.0.0.0:5000 --timeout 600 --workers 1 --threads 4 --access-logfile - --error-logfile - app:app"
```

#### Step 6: Enable Logging

```bash
# Enable container logging
az webapp log config \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP \
  --docker-container-logging filesystem

# Stream logs
az webapp log tail \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP
```

#### Step 7: Test Deployment

```bash
# Get App Service URL
APP_URL="https://$(az webapp show --resource-group $RESOURCE_GROUP --name $APP_SERVICE --query 'defaultHostName' -o tsv)"

echo "App URL: $APP_URL"

# Test API endpoint
curl "$APP_URL/api/DocumentEditor/Process"

# Test frontend
curl "$APP_URL/"
```

#### Step 8: Configure Custom Domain (Optional)

```bash
# Add custom domain
az webapp config hostname add \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP \
  --hostname yourdomain.com

# Create SSL binding (requires certificate)
az webapp config ssl bind \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP \
  --certificate-thumbprint <thumbprint>
```

---

### 8.3 Continuous Deployment (CI/CD)

#### GitHub Actions Example

**File: `.github/workflows/deploy-to-azure.yml`**

```yaml
name: Build and Deploy to Azure App Service

on:
  push:
    branches: [ main, EJ2-1055046-hosting ]
    paths:
      - 'frontend/**'
      - 'app.py'
      - 'requirements.txt'
      - 'NETStandardWrapperLibrary/**'
      - 'Dockerfile'

env:
  REGISTRY_NAME: spreadsheetacr
  IMAGE_NAME: spreadsheet-app
  RESOURCE_GROUP: rg-spreadsheet-prod
  APP_SERVICE: spreadsheet-app-service

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Login to ACR
      uses: azure/docker-login@v1
      with:
        login-server: ${{ env.REGISTRY_NAME }}.azurecr.io
        username: ${{ secrets.ACR_USERNAME }}
        password: ${{ secrets.ACR_PASSWORD }}
    
    - name: Build and push Docker image
      run: |
        docker build \
          --build-arg VITE_APP_BASE_PATH='' \
          -t ${{ env.REGISTRY_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:${{ github.sha }} \
          -t ${{ env.REGISTRY_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:latest \
          .
        
        docker push ${{ env.REGISTRY_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:${{ github.sha }}
        docker push ${{ env.REGISTRY_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:latest
    
  deploy:
    needs: build
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Login to Azure
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}
    
    - name: Deploy to App Service
      uses: azure/webapps-deploy@v2
      with:
        app-name: ${{ env.APP_SERVICE }}
        images: ${{ env.REGISTRY_NAME }}.azurecr.io/${{ env.IMAGE_NAME }}:latest
        resource-group: ${{ env.RESOURCE_GROUP }}
```

---

## 9. Docker Compose Setup (Local Testing)

### 9.1 docker-compose.yml

Create `docker-compose.yml` for local development and testing:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: spreadsheet-redis
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        VITE_APP_BASE_PATH: ''
    container_name: spreadsheet-app
    ports:
      - "5000:5000"
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=
      - REDIS_SSL=false
      - PYTHONNET_RUNTIME=coreclr
      - DOTNET_ROOT=/usr/share/dotnet
      - BASE_PATH=
      - BACKEND_URL=http://localhost:5000/
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./Files:/app/Files
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/DocumentEditor/Process"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

volumes:
  redis-data:

networks:
  default:
    name: spreadsheet-network
```

### 9.2 Local Testing Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f app

# Test API
curl http://localhost:5000/api/DocumentEditor/Process

# Test frontend
curl http://localhost:5000/

# Stop services
docker-compose down

# Clean up volumes
docker-compose down -v
```

---

## 10. Configuration Management

### 10.1 Environment Variable Injection Strategies

#### Strategy 1: Azure App Service (Recommended)

**Advantages:**
- ✅ Managed by Azure
- ✅ No secrets in code
- ✅ Supports Key Vault integration
- ✅ Easy to rotate credentials

**Steps:**

```bash
az webapp config appsettings set \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP \
  --settings \
    REDIS_HOST="your-redis.redis.cache.windows.net" \
    REDIS_PORT="6380" \
    REDIS_PASSWORD="your-password" \
    REDIS_SSL="true" \
    SYNCFUSION_LICENSE_KEY="your-license-key" \
    BACKEND_URL="https://your-app.azurewebsites.net/"
```

#### Strategy 2: Key Vault (Enterprise)

**Setup:**

```bash
# Create Key Vault
az keyvault create \
  --name "spreadsheet-kv" \
  --resource-group $RESOURCE_GROUP

# Store secrets
az keyvault secret set \
  --vault-name "spreadsheet-kv" \
  --name "redis-password" \
  --value "your-password"

# Grant App Service access
PRINCIPAL_ID=$(az webapp identity assign \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP \
  --query principalId -o tsv)

az keyvault set-policy \
  --name "spreadsheet-kv" \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get

# Reference in app settings
az webapp config appsettings set \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP \
  --settings \
    REDIS_PASSWORD="@Microsoft.KeyVault(SecretUri=https://spreadsheet-kv.vault.azure.net/secrets/redis-password/)"
```

#### Strategy 3: .env File (Development Only)

**File: `.env` (git-ignored)**

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_SSL=false
SYNCFUSION_LICENSE_KEY=your-dev-license
BACKEND_URL=http://localhost:5000/
```

**Load in Dockerfile:**

```dockerfile
# This is NOT recommended for production, use for local dev only
RUN if [ -f .env ]; then set -a && source .env && set +a; fi
```

### 10.2 Secret Rotation

**Rotate Redis Password:**

```bash
# Generate new password in Azure Redis
az redis update \
  --name $REDIS_NAME \
  --resource-group $RESOURCE_GROUP \
  --notify-keyspace-events "Ex"

# Get new password
NEW_PASSWORD=$(az redis list-keys \
  --resource-group $RESOURCE_GROUP \
  --name $REDIS_NAME \
  --query "primaryKey" -o tsv)

# Update App Service
az webapp config appsettings set \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP \
  --settings \
    REDIS_PASSWORD="$NEW_PASSWORD"

# App Service will restart automatically
```

---

## 11. Validation Checklist

### 11.1 Pre-Deployment Verification

**Code Quality:**
- [ ] No hardcoded credentials in code or git history
- [ ] Environment variables are documented
- [ ] Docker images build without errors
- [ ] No warnings during npm/pip installs
- [ ] TypeScript compiles without errors
- [ ] Linting passes (if configured)

**Docker Image:**
- [ ] Image size is reasonable (<2GB)
- [ ] Healthcheck is responsive
- [ ] Container starts within 30 seconds
- [ ] Logs show no critical errors
- [ ] All dependencies installed correctly

**API Functionality:**
- [ ] `/api/DocumentEditor/Process` endpoint responds
- [ ] Frontend loads without 404s
- [ ] WebSocket connections work (if testable locally)
- [ ] Redis connection succeeds
- [ ] License key registers (if applicable)

**Configuration:**
- [ ] Redis host/port/password correct
- [ ] Syncfusion license key valid
- [ ] BACKEND_URL points to correct server
- [ ] All env vars injected properly

### 11.2 Post-Deployment Verification

**Azure Resources:**
```bash
# Check App Service status
az webapp show --name $APP_SERVICE --resource-group $RESOURCE_GROUP --query "state" -o tsv

# View recent deployments
az webapp deployment list --name $APP_SERVICE --resource-group $RESOURCE_GROUP

# Check container logs
az webapp log tail --name $APP_SERVICE --resource-group $RESOURCE_GROUP
```

**Endpoint Testing:**
```bash
# Get app URL
APP_URL="https://$(az webapp show --resource-group $RESOURCE_GROUP --name $APP_SERVICE --query 'defaultHostName' -o tsv)"

# Test API
curl "$APP_URL/api/DocumentEditor/Process"

# Test frontend load
curl -I "$APP_URL/"

# Check response headers
curl -I "$APP_URL/" | grep -i "content-type"
```

**Performance Testing:**
```bash
# Load test (requires Apache Bench or similar)
ab -n 100 -c 10 "$APP_URL/api/DocumentEditor/Process"

# Monitor in Azure Portal
# - App Service → Metrics
# - HTTP Server Errors
# - Response Time
# - CPU Percentage
```

---

## 12. Risks and Recommendations

### 12.1 Identified Risks

| Risk | Severity | Impact | Mitigation |
|------|----------|--------|-----------|
| **Hardcoded Frontend URL** | HIGH | Frontend won't work in production | Implement dynamic URL injection (Section 5) |
| **Exposed Redis Credentials** | CRITICAL | Security breach, data compromise | Move to env vars / Key Vault (Section 10) |
| **Missing License Key Validation** | HIGH | Syncfusion errors at runtime | Inject SYNCFUSION_LICENSE_KEY env var |
| **Large Docker Image** | MEDIUM | Slow deployment, high bandwidth | Already optimized; consider Alpine Python |
| **Single Container Failure** | MEDIUM | Complete downtime | Implement health checks, auto-restart policy |
| **No Data Persistence** | MEDIUM | Version history lost on redeploy | Configure persistent storage in App Service |
| **Gunicorn Single Worker** | MEDIUM | Limited concurrency | Increase workers or use load balancing |
| **Cross-Origin Issues** | MEDIUM | Frontend CORS errors | CORS configured in app.py (open, consider restricting) |

### 12.2 Security Recommendations

**Immediate Actions:**
1. ✅ Move Redis credentials to environment variables
2. ✅ Rotate Azure Redis primary/secondary keys
3. ✅ Restrict CORS to specific origins (not `*`)
4. ✅ Enable HTTPS only on App Service
5. ✅ Configure network restrictions (VNets, service endpoints)

**Short-term (1-2 weeks):**
1. ✅ Implement Azure Key Vault for secrets
2. ✅ Add request authentication (OAuth, JWT)
3. ✅ Enable diagnostic logging to Storage Account
4. ✅ Set up Azure Monitor alerts for errors

**Long-term (1-3 months):**
1. ✅ Implement API rate limiting
2. ✅ Add request validation / input sanitization
3. ✅ Implement audit logging
4. ✅ Conduct security penetration testing

### 12.3 Performance Recommendations

**Scaling Strategy:**
- **Current:** B2 App Service plan with 1 Gunicorn worker
- **Growth:** Move to P1v2 (Premium) with 2-4 workers + Application Gateway

**Optimization:**
```bash
# Increase Gunicorn workers for more concurrency
CMD ["gunicorn",
     "--bind","0.0.0.0:5000",
     "--timeout","600",
     "--workers","4",        # Increase from 1
     "--threads","4",
     "--worker-class","gthread",  # Use threaded worker
     "--max-requests","1000",
     "--access-logfile","-",
     "--error-logfile","-",
     "app:app"]
```

**Caching:**
- Implement Redis caching for collaborative session state
- Add CDN for static frontend assets
- Enable HTTP caching headers on frontend

### 12.4 Backup and Disaster Recovery

**Version History Backup:**
```bash
# Backup Redis data
az redis export \
  --name $REDIS_NAME \
  --resource-group $RESOURCE_GROUP \
  --files /uploads/export.rdb \
  --file-format rdb

# Automate daily backups with Azure Backup
```

**Database Snapshots:**
```bash
# Enable geo-replication for Redis
az redis update \
  --name $REDIS_NAME \
  --resource-group $RESOURCE_GROUP \
  --enable-non-ssl-port false \
  --replicate-to-linked \
  --link-to "spreadsheet-redis-replica"
```

### 12.5 Monitoring and Alerts

**Create Alert Rules:**

```bash
# Alert on high error rate
az monitor metrics alert create \
  --name "Spreadsheet-HighErrorRate" \
  --resource-group $RESOURCE_GROUP \
  --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$APP_SERVICE" \
  --condition "avg Http5xx > 10" \
  --description "Alert when >10 HTTP 5xx errors in 5 minutes" \
  --evaluation-frequency 5m \
  --window-size 5m \
  --actions "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/microsoft.insights/actionGroups/DefaultActionGroup"

# Alert on high CPU
az monitor metrics alert create \
  --name "Spreadsheet-HighCPU" \
  --resource-group $RESOURCE_GROUP \
  --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$APP_SERVICE" \
  --condition "avg CpuPercentage > 80" \
  --evaluation-frequency 5m \
  --window-size 5m \
  --actions "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/microsoft.insights/actionGroups/DefaultActionGroup"
```

---

## 13. Troubleshooting Guide

### Common Issues and Solutions

**Issue: "Cannot connect to Redis"**
```
Error: Configure Redis.Host in appsettings.json
Solution:
1. Check REDIS_HOST env var is set: az webapp config appsettings list
2. Verify Redis status: az redis show --name $REDIS_NAME
3. Check firewall rules: az redis firewall-rules list
4. Test locally with docker-compose
```

**Issue: "Frontend shows blank page"**
```
Solution:
1. Check browser console for errors (F12 → Console)
2. Verify BACKEND_URL env var
3. Check CORS headers in response
4. Look for 404 on static assets in Network tab
```

**Issue: "Container fails to start"**
```
Check logs:
az webapp log tail --name $APP_SERVICE

Common causes:
- Missing .NET runtime: Check base image
- Missing Python packages: pip install fails
- Corrupted license file: Verify license content
- Port 5000 already in use: Check firewall
```

**Issue: "Timeout on large file upload"**
```
Solution in Dockerfile/Gunicorn:
--timeout 600  (already set to 10 minutes)
Increase if needed:
--timeout 1200  (20 minutes)
```

---

## 14. References and Additional Resources

**Official Documentation:**
- [Azure App Service Docker Documentation](https://learn.microsoft.com/en-us/azure/app-service/configure-custom-container)
- [Azure Container Registry Documentation](https://learn.microsoft.com/en-us/azure/container-registry/)
- [Azure Redis Cache Documentation](https://learn.microsoft.com/en-us/azure/azure-cache-for-redis/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Vue.js Documentation](https://vuejs.org/)
- [Syncfusion Spreadsheet Documentation](https://www.syncfusion.com/vue-components/vue-spreadsheet)

**Docker Best Practices:**
- [Docker Official Images](https://hub.docker.com/r/microsoft/dotnet/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Multi-Stage Build Optimization](https://docs.docker.com/build/building/multi-stage/)

**Azure CLI Reference:**
- [az webapp command reference](https://learn.microsoft.com/en-us/cli/azure/webapp)
- [az acr command reference](https://learn.microsoft.com/en-us/cli/azure/acr)
- [az redis command reference](https://learn.microsoft.com/en-us/cli/azure/redis)

---

## Appendix A: Complete Environment Variables

### All Environment Variables Required

```bash
# ============================================
# Redis Configuration (REQUIRED)
# ============================================
REDIS_HOST=your-redis.redis.cache.windows.net
REDIS_PORT=6380
REDIS_PASSWORD=your-redis-primary-key
REDIS_SSL=true

# ============================================
# Syncfusion License (REQUIRED)
# ============================================
SYNCFUSION_LICENSE_KEY=your-license-key-here

# ============================================
# Frontend Configuration (REQUIRED for production)
# ============================================
BACKEND_URL=https://your-app.azurewebsites.net/

# ============================================
# Python/.NET Runtime (SET IN DOCKERFILE)
# ============================================
PYTHONNET_RUNTIME=coreclr
PYTHONUNBUFFERED=1
DOTNET_ROOT=/usr/share/dotnet
DOTNET_ROLL_FORWARD=LatestMajor

# ============================================
# Optional / Advanced
# ============================================
BASE_PATH=                           # For sub-path routing
VITE_APP_BASE_PATH=                  # Frontend asset base
WEBSITES_ENABLE_APP_SERVICE_STORAGE=false  # Azure App Service
WEBSITES_PORT=5000                   # Azure App Service
```

---

## Appendix B: Quick Start Script

**File: `scripts/deploy-to-azure.sh`**

```bash
#!/bin/bash
set -e

# Quick deployment script
# Usage: ./scripts/deploy-to-azure.sh <resource-group> <app-name> <license-key>

RESOURCE_GROUP=${1:-"rg-spreadsheet-prod"}
APP_NAME=${2:-"spreadsheet-app"}
LICENSE_KEY=${3:-""}
LOCATION="eastus"

ACR_NAME="${APP_NAME}acr"
REDIS_NAME="${APP_NAME}-redis"
APP_SERVICE_PLAN="${APP_NAME}-plan"
APP_SERVICE="${APP_NAME}-service"

echo "═══════════════════════════════════════════════════════════════"
echo "Deploying Spreadsheet Application to Azure"
echo "═══════════════════════════════════════════════════════════════"
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "App Name: $APP_NAME"
echo ""

# Create resources
echo "[1/5] Creating Azure resources..."
az group create --name $RESOURCE_GROUP --location $LOCATION 2>/dev/null || true
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic 2>/dev/null || true
az redis create --resource-group $RESOURCE_GROUP --name $REDIS_NAME --location $LOCATION --sku Basic --vm-size c0 2>/dev/null || true
az appservice plan create --name $APP_SERVICE_PLAN --resource-group $RESOURCE_GROUP --sku B2 --is-linux 2>/dev/null || true
az webapp create --resource-group $RESOURCE_GROUP --plan $APP_SERVICE_PLAN --name $APP_SERVICE 2>/dev/null || true

# Build and push image
echo "[2/5] Building and pushing Docker image..."
az acr login --name $ACR_NAME
docker build -t $ACR_NAME.azurecr.io/$APP_NAME:latest .
docker push $ACR_NAME.azurecr.io/$APP_NAME:latest

# Get credentials
echo "[3/5] Retrieving Azure credentials..."
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query "username" -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)
REDIS_HOST=$(az redis show --resource-group $RESOURCE_GROUP --name $REDIS_NAME --query "hostName" -o tsv)
REDIS_PASSWORD=$(az redis list-keys --resource-group $RESOURCE_GROUP --name $REDIS_NAME --query "primaryKey" -o tsv)

# Configure App Service
echo "[4/5] Configuring App Service..."
az webapp config container set \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name "$ACR_NAME.azurecr.io/$APP_NAME:latest" \
  --docker-registry-server-url "https://$ACR_NAME.azurecr.io" \
  --docker-registry-server-user "$ACR_USERNAME" \
  --docker-registry-server-password "$ACR_PASSWORD"

# Set app settings
echo "[5/5] Setting environment variables..."
az webapp config appsettings set \
  --name $APP_SERVICE \
  --resource-group $RESOURCE_GROUP \
  --settings \
    REDIS_HOST="$REDIS_HOST" \
    REDIS_PORT="6380" \
    REDIS_PASSWORD="$REDIS_PASSWORD" \
    REDIS_SSL="true" \
    SYNCFUSION_LICENSE_KEY="$LICENSE_KEY" \
    BACKEND_URL="https://$APP_SERVICE.azurewebsites.net/" \
    WEBSITES_PORT="5000"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "Deployment Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo "App URL: https://$APP_SERVICE.azurewebsites.net"
echo "View logs: az webapp log tail --name $APP_SERVICE --resource-group $RESOURCE_GROUP"
```

---

**End of Deployment Guide**
