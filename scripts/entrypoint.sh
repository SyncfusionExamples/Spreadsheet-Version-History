#!/bin/bash
# ============================================================================
# Entrypoint Script - Configuration Injection and Application Startup
# ============================================================================
# This script handles:
# 1. Environment variable validation
# 2. Configuration injection into frontend
# 3. Health checks on startup
# 4. Application startup with proper error handling
#
# Environment Variables (all optional, with sensible defaults):
#   REDIS_HOST              - Redis hostname (default: localhost)
#   REDIS_PORT              - Redis port (default: 6379)
#   REDIS_PASSWORD          - Redis password (default: empty)
#   REDIS_SSL               - Use SSL (default: false)
#   SYNCFUSION_LICENSE_KEY  - License key (optional)
#   BACKEND_URL             - Frontend API endpoint (default: http://localhost:5000/)
#   BASE_PATH               - Sub-path routing (default: empty)
#   GUNICORN_WORKERS        - Worker count (default: 1)
# ============================================================================

set -e

echo "=========================================="
echo "Spreadsheet App - Startup Configuration"
echo "=========================================="
echo "$(date '+%Y-%m-%d %H:%M:%S') [startup] Starting application..."

# ---- 1. Validate Environment ----
echo "[startup] Validating environment..."

# Set defaults for Redis
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}
REDIS_PASSWORD=${REDIS_PASSWORD:-}
REDIS_SSL=${REDIS_SSL:-false}
BASE_PATH=${BASE_PATH:-}
BACKEND_URL=${BACKEND_URL:-http://localhost:5000/}

echo "[config] Redis Host: $REDIS_HOST:$REDIS_PORT"
echo "[config] Redis SSL: $REDIS_SSL"
echo "[config] Backend URL: $BACKEND_URL"

if [ -z "$REDIS_HOST" ]; then
    echo "[ERROR] REDIS_HOST is required but not set"
    exit 1
fi

# ---- 2. Update appsettings.json with Environment Variables ----
echo "[config] Updating appsettings.json with environment variables..."

if [ ! -f /app/appsettings.json ]; then
    echo "[ERROR] appsettings.json not found"
    exit 1
fi

# Create a temporary Python script to update JSON safely
python3 << 'PYTHON_SCRIPT'
import json
import os

settings_file = '/app/appsettings.json'

try:
    with open(settings_file, 'r', encoding='utf-8') as f:
        settings = json.load(f)
except Exception as e:
    print(f"[ERROR] Failed to read {settings_file}: {e}")
    exit(1)

# Ensure Redis section exists
if 'Redis' not in settings:
    settings['Redis'] = {}

# Update Redis configuration from environment variables
redis_host = os.environ.get('REDIS_HOST', 'localhost').strip()
redis_port = int(os.environ.get('REDIS_PORT', '6379'))
redis_password = os.environ.get('REDIS_PASSWORD', '').strip()
redis_ssl = os.environ.get('REDIS_SSL', 'false').lower() in ('true', '1', 'yes')

settings['Redis']['Host'] = redis_host
settings['Redis']['Port'] = redis_port
settings['Redis']['Password'] = redis_password
settings['Redis']['Ssl'] = redis_ssl

# Write back safely
try:
    with open(settings_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    print(f"[config] appsettings.json updated: {redis_host}:{redis_port}, SSL={redis_ssl}")
except Exception as e:
    print(f"[ERROR] Failed to write {settings_file}: {e}")
    exit(1)
PYTHON_SCRIPT

if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to update configuration"
    exit 1
fi

# ---- 3. Inject Backend URL into Frontend (if HTML exists) ----
echo "[config] Configuring frontend..."

FRONTEND_HTML="/app/frontend/dist/index.html"
if [ -f "$FRONTEND_HTML" ]; then
    # Inject a configuration script into the HTML before app loads
    # This allows the frontend to discover the backend URL at runtime
    
    BACKEND_CONFIG="<script>window.__BACKEND_URL__='${BACKEND_URL}';</script>"
    
    # Check if config already exists (idempotent)
    if ! grep -q "__BACKEND_URL__" "$FRONTEND_HTML"; then
        # Insert config before closing head tag
        sed -i "s|</head>|${BACKEND_CONFIG}</head>|" "$FRONTEND_HTML" 2>/dev/null || {
            echo "[warn] Could not inject backend config into HTML"
        }
    fi
    echo "[config] Frontend configured with backend URL: $BACKEND_URL"
else
    echo "[warn] Frontend dist not found at $FRONTEND_HTML"
fi

# ---- 4. Log Important Diagnostics ----
echo "[startup] ========== Diagnostics =========="
echo "[startup] Python version: $(python3 --version)"
echo "[startup] Working directory: $(pwd)"
echo "[startup] Files in /app:"
ls -la /app/ | head -20
echo "[startup] Frontend dist exists: $([ -d /app/frontend/dist ] && echo 'yes' || echo 'no')"
echo "[startup] .NET binaries: $([ -f /app/NETStandardWrapperLibrary/WebServiceLibrary/bin/Release/net10.0/publish/WebServiceLibrary.dll ] && echo 'found' || echo 'NOT FOUND')"
echo "[startup] ========== End Diagnostics =========="

# ---- 5. Pre-flight Checks ----
echo "[startup] Running pre-flight checks..."

# Check Redis connectivity (non-blocking; continues even if fails)
python3 << 'REDIS_CHECK'
import redis
import os

try:
    redis_host = os.environ.get('REDIS_HOST', 'localhost')
    redis_port = int(os.environ.get('REDIS_PORT', '6379'))
    redis_password = os.environ.get('REDIS_PASSWORD', '').strip() or None
    redis_ssl = os.environ.get('REDIS_SSL', 'false').lower() in ('true', '1', 'yes')
    
    print(f"[preflight] Testing Redis connection to {redis_host}:{redis_port} (SSL={redis_ssl})...")
    
    client = redis.Redis(
        host=redis_host,
        port=redis_port,
        password=redis_password,
        ssl=redis_ssl,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    
    client.ping()
    print(f"[preflight] ✓ Redis connection successful")
    
except redis.ConnectionError as e:
    print(f"[preflight] ⚠ Redis connection failed (non-blocking): {e}")
    print(f"[preflight]   App will continue; Redis connection will be retried by application")
except Exception as e:
    print(f"[preflight] ⚠ Redis check error: {e}")
REDIS_CHECK

# ---- 6. Start Application ----
echo "[startup] =========================================="
echo "[startup] Starting Flask application with Gunicorn..."
echo "[startup] =========================================="

# Export for child process
export PYTHONUNBUFFERED=1
export PYTHONNET_RUNTIME=coreclr
export DOTNET_ROOT=/usr/share/dotnet
export DOTNET_ROLL_FORWARD=LatestMajor

# Execute the main command (passed as arguments)
exec "$@"
