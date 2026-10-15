# Environment Variables Reference

Complete guide to all environment variables used by the Spreadsheet application.

## Quick Start (Local Development)

```bash
# Copy and customize
cp .env.example .env

# Load environment
export $(cat .env | grep -v '#' | xargs)

# Start containers
docker-compose up -d
```

---

## Configuration Variables

### Redis Configuration

Essential for collaborative editing and session management.

| Variable | Type | Required | Default | Example | Notes |
|----------|------|----------|---------|---------|-------|
| `REDIS_HOST` | String | ✅ Yes | N/A | `redis-cache.redis.cache.windows.net` | Hostname of Redis server. For Docker Compose, use `redis`. For Azure, use `<name>.redis.cache.windows.net` |
| `REDIS_PORT` | Integer | Optional | `6379` | `6380` | Port number. Azure uses 6380 for SSL connections. |
| `REDIS_PASSWORD` | String | Depends | Empty | `your-access-key` | Required for Azure Redis. Leave empty for local development. |
| `REDIS_SSL` | Boolean | Optional | `false` | `true` | Enable SSL/TLS. Use `true` for Azure, `false` for local Redis. |

**Local Development:**
```bash
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_SSL=false
```

**Azure Production:**
```bash
REDIS_HOST=myapp-redis.redis.cache.windows.net
REDIS_PORT=6380
REDIS_PASSWORD=<your-redis-primary-key>
REDIS_SSL=true
```

### Syncfusion License

| Variable | Type | Required | Default | Notes |
|----------|------|----------|---------|-------|
| `SYNCFUSION_LICENSE_KEY` | String | ✅ Yes | N/A | Your Syncfusion Essential Studio license key. Contact sales@syncfusion.com for commercial licensing. |

**Obtaining a License:**
1. Visit [Syncfusion Licensing](https://www.syncfusion.com/content/downloads/syncfusion_license.pdf)
2. Register for [Community License](https://www.syncfusion.com/products/communitylicense) if eligible
3. Retrieve your license key from your account dashboard

### Frontend Configuration

| Variable | Type | Set By | Default | Notes |
|----------|------|--------|---------|-------|
| `VITE_APP_BASE_PATH` | String | Docker build arg | `''` | Base path for static assets (e.g., `/spreadsheet/` for sub-path deployment). Set at **build time**, not runtime. |
| `BACKEND_URL` | String | Environment | `http://127.0.0.1:5000/` | URL where frontend can reach the Flask backend. Injected at startup via entrypoint script. |

**Build-time Configuration:**
```bash
# Build with custom base path for sub-path deployment
docker build --build-arg VITE_APP_BASE_PATH='/app/' -t myapp:latest .
```

**Runtime Configuration:**
```bash
# Set backend URL for your deployment
BACKEND_URL=https://myapp.azurewebsites.net/ docker-compose up
```

### Python/Flask Configuration

| Variable | Type | Set By | Default | Notes |
|----------|------|--------|---------|-------|
| `PYTHONUNBUFFERED` | Boolean | Dockerfile | `1` | Ensures Python output is flushed immediately. Required for Docker logging. |
| `BASE_PATH` | String | Environment | `''` | URL sub-path for routing through load balancers (e.g., `/api` mounts app at `/api`). |

### .NET Runtime Configuration

| Variable | Type | Set By | Default | Notes |
|----------|------|--------|---------|-------|
| `PYTHONNET_RUNTIME` | String | app.py / Dockerfile | `coreclr` | Python.NET runtime. Must be `coreclr` for Linux .NET Core. |
| `DOTNET_ROOT` | String | Dockerfile | `/usr/share/dotnet` | Path to .NET runtime. Auto-detected if not set. |
| `DOTNET_ROLL_FORWARD` | String | app.py / Dockerfile | `LatestMajor` | Allows net10.0 code to run on newer .NET versions. |
| `LD_LIBRARY_PATH` | String | Dockerfile | (complex) | Native library search paths for SkiaSharp, graphics libs. Set in Dockerfile. |

### Azure App Service Specific

| Variable | Type | Set By | Default | Notes |
|----------|------|--------|---------|-------|
| `WEBSITES_PORT` | Integer | Azure | `5000` | Port container listens on. Must match EXPOSE in Dockerfile. |
| `WEBSITES_ENABLE_APP_SERVICE_STORAGE` | Boolean | Azure | `true` | Enable persistent storage. Set to `false` for read-only container. |

---

## Environment Files

### .env.example (Template)

Create `.env` (git-ignored) based on this template:

```bash
# ============================================================================
# Local Development Environment Variables
# ============================================================================
# Copy this file to .env and customize for your setup
# .env is git-ignored and never committed

# ---- Redis Configuration (Local) ----
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_SSL=false

# ---- Syncfusion License ----
# Get from: https://www.syncfusion.com
SYNCFUSION_LICENSE_KEY=your-license-key-here

# ---- Frontend Configuration ----
VITE_APP_BASE_PATH=
BACKEND_URL=http://localhost:5000/

# ---- Python Runtime ----
PYTHONUNBUFFERED=1
BASE_PATH=

# ---- Optional: Gunicorn Tuning ----
GUNICORN_WORKERS=1
GUNICORN_THREADS=4
```

### .env.production.example (Azure Template)

Template for production environment:

```bash
# ============================================================================
# Production Environment Variables (Azure App Service)
# ============================================================================
# Set these via Azure Portal or Azure CLI:
#   az webapp config appsettings set --name <app> --resource-group <rg> \
#     --settings REDIS_HOST="..." REDIS_PASSWORD="..." ...

# ---- Redis Configuration (Azure) ----
REDIS_HOST=myapp-redis.redis.cache.windows.net
REDIS_PORT=6380
REDIS_PASSWORD=<your-redis-primary-key>
REDIS_SSL=true

# ---- Syncfusion License ----
SYNCFUSION_LICENSE_KEY=<your-production-license-key>

# ---- Frontend Configuration ----
VITE_APP_BASE_PATH=
BACKEND_URL=https://myapp.azurewebsites.net/

# ---- Application Settings ----
PYTHONUNBUFFERED=1
BASE_PATH=

# ---- Gunicorn Tuning (for production) ----
GUNICORN_WORKERS=4
GUNICORN_THREADS=4
```

---

## Setting Environment Variables

### Method 1: Docker Compose (Local Development)

Edit `docker-compose.yml` environment section:

```yaml
environment:
  REDIS_HOST: redis
  REDIS_PORT: "6379"
  REDIS_PASSWORD: ""
  SYNCFUSION_LICENSE_KEY: "your-key"
```

### Method 2: Command Line (Docker)

```bash
docker run -e REDIS_HOST=redis -e SYNCFUSION_LICENSE_KEY=... myapp:latest
```

### Method 3: .env File + Docker Compose

```bash
# Create .env file
echo "REDIS_HOST=myredis" > .env
echo "SYNCFUSION_LICENSE_KEY=mykey" >> .env

# Docker Compose automatically loads .env
docker-compose up
```

### Method 4: Azure App Service (Production)

```bash
# View current settings
az webapp config appsettings list --name myapp --resource-group myrg

# Add/update settings
az webapp config appsettings set --name myapp --resource-group myrg --settings \
  REDIS_HOST="myredis.redis.cache.windows.net" \
  REDIS_PORT="6380" \
  REDIS_PASSWORD="mykey" \
  REDIS_SSL="true" \
  SYNCFUSION_LICENSE_KEY="mykey" \
  BACKEND_URL="https://myapp.azurewebsites.net/"

# Delete setting
az webapp config appsettings delete --name myapp --resource-group myrg --setting-names OLD_VAR
```

### Method 5: Azure Key Vault (Enterprise)

```bash
# Create secret in Key Vault
az keyvault secret set --vault-name mykv --name redis-password --value "mypassword"

# Reference in App Service (format: @Microsoft.KeyVault(...))
az webapp config appsettings set --name myapp --resource-group myrg --settings \
  REDIS_PASSWORD="@Microsoft.KeyVault(SecretUri=https://mykv.vault.azure.net/secrets/redis-password/)"
```

---

## Validation and Troubleshooting

### Check Current Environment

```bash
# Docker container
docker exec spreadsheet-app env | grep REDIS

# Azure App Service
az webapp config appsettings list --name myapp --resource-group myrg

# Local development
env | grep -E "REDIS|SYNCFUSION|BACKEND"
```

### Test Redis Connection

```bash
# From application container
docker exec spreadsheet-app python3 << 'EOF'
import redis
import os

client = redis.Redis(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=int(os.environ.get('REDIS_PORT', '6379')),
    password=os.environ.get('REDIS_PASSWORD'),
    ssl=os.environ.get('REDIS_SSL', 'false') == 'true'
)
print("Redis connection:", client.ping())
EOF
```

### View Application Logs

```bash
# Docker Compose
docker-compose logs -f app

# Azure App Service
az webapp log tail --name myapp --resource-group myrg

# Stream in real-time
az webapp log tail --name myapp --resource-group myrg --follow
```

---

## Security Best Practices

### ✅ DO

- ✅ Use environment variables for all secrets
- ✅ Store sensitive values in Azure Key Vault
- ✅ Rotate Redis password regularly
- ✅ Use SSL/TLS for Redis in production
- ✅ Never commit `.env` files to git
- ✅ Use separate credentials for dev/test/prod

### ❌ DON'T

- ❌ Hardcode credentials in code
- ❌ Commit credentials to git (even in history)
- ❌ Use same password across environments
- ❌ Log sensitive values
- ❌ Share credentials via email/chat
- ❌ Disable SSL in production

---

## Secrets Rotation

### Rotate Redis Password

```bash
# 1. Generate new password in Azure Redis (automatic)
# 2. Update App Service setting
REDIS_PASSWORD=$(az redis list-keys --name myredis --resource-group myrg --query primaryKey -o tsv)

az webapp config appsettings set --name myapp --resource-group myrg --settings \
  REDIS_PASSWORD="$REDIS_PASSWORD"

# 3. App Service automatically restarts with new password
```

### Rotate Syncfusion License

```bash
az webapp config appsettings set --name myapp --resource-group myrg --settings \
  SYNCFUSION_LICENSE_KEY="new-license-key"
```

---

## References

- [Syncfusion Licensing](https://www.syncfusion.com/licensing/)
- [Azure App Service Environment Variables](https://learn.microsoft.com/en-us/azure/app-service/reference-app-settings-secure-env-variables)
- [Azure Redis Cache](https://learn.microsoft.com/en-us/azure/azure-cache-for-redis/)
- [Docker Environment Variables](https://docs.docker.com/compose/environment-variables/)
