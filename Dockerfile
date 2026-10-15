# ---- 1. Build Vue frontend ----
FROM node:20-alpine AS frontend

# Build argument for SPA base path
# Usage: docker build --build-arg VITE_APP_BASE_PATH='/vue-spreadsheet-docx-mail-merge/' ...
# Default: Empty string (serves at root '/')
ARG VITE_APP_BASE_PATH=''

WORKDIR /fe
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./

# Build Vue app with the base path
# The base path affects asset URLs and Vue Router
# Does NOT affect API endpoint paths (those remain at root)
RUN VITE_APP_BASE_PATH=$VITE_APP_BASE_PATH npm run build

# ---- 2. Publish .NET wrapper ----
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS dotnet
WORKDIR /src
COPY "NETStandardWrapperLibrary/WebServiceLibrary/" ./
RUN dotnet publish WebServiceLibrary.csproj -c Release -o /out
# output: /out/

# ---- 3. Runtime ----
# Use official .NET 10 aspnet image (includes runtime and more libs)
FROM mcr.microsoft.com/dotnet/aspnet:10.0

# Install system dependencies including graphics libraries required for PDF export
# SkiaSharp (used for PDF rendering) requires these native libraries
# Ubuntu 22.04 - using only stable, readily available packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    curl \
    libgdiplus \
    fontconfig \
    libfreetype6 \
    libharfbuzz0b \
    libfontconfig1 \
    libssl3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
ENV PYTHONNET_RUNTIME=coreclr
ENV DOTNET_ROOT=/usr/share/dotnet

# SkiaSharp environment variables for proper native library loading
# Include both system graphics paths AND the publish folder (which has libSkiaSharp.so)
ENV LD_LIBRARY_PATH=/app/NETStandardWrapperLibrary/WebServiceLibrary/bin/Release/net10.0/publish/runtimes/linux-x64/native:/app/NETStandardWrapperLibrary/WebServiceLibrary/bin/Release/net10.0/publish:/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu
ENV SKIASHARP_NATIVE_DIR=/usr/lib/x86_64-linux-gnu

WORKDIR /app

# Set up Python virtual environment first
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy configuration and app files
COPY app.py .
COPY appsettings.json .
COPY Files ./Files

# Copy compiled frontend dist
COPY --from=frontend /fe/dist ./frontend/dist

# Copy .NET wrapper published binaries (includes managed DLLs and dependencies)
# Copies from build stage: /out/* → /app/NETStandardWrapperLibrary/WebServiceLibrary/bin/Release/net10.0/publish/
COPY --from=dotnet /out ./NETStandardWrapperLibrary/WebServiceLibrary/bin/Release/net10.0/publish/

# NOTE: The /out/runtimes folder (containing libSkiaSharp.so) is included in the above COPY
# because COPY recursively includes all subdirectories

EXPOSE 5000

# ---------------------------------------------------------------------------
# Runtime configuration via environment variables
#
# From Azure App Service Environment Variables (Settings → Configuration):
#   SYNCFUSION_LICENSE_KEY              → Syncfusion.LicenseKey
#   AZURE_OPENAI_ENDPOINT               → AzureOpenAI.Endpoint
#   AZURE_OPENAI_API_KEY                → AzureOpenAI.ApiKey
#   AZURE_OPENAI_DEPLOYMENT_NAME        → AzureOpenAI.DeploymentName
#   AZURE_OPENAI_API_VERSION (optional) → AzureOpenAI.ApiVersion (default 2024-02-15-preview)
#
# The app.py reads environment variables first, then falls back to
# appsettings.json values. Env vars take precedence in container/CI.
#
# Example Azure CLI deployment:
#   az container create \
#     --resource-group <rg> \
#     --name <name> \
#     --image <acr>.azurecr.io/rentroll-app:latest \
#     --ports 5000 \
#     --environment-variables \
#       SYNCFUSION_LICENSE_KEY="<key>" \
#       AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com/" \
#       AZURE_OPENAI_API_KEY="<key>" \
#       AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o"
# ---------------------------------------------------------------------------

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/api/DocumentEditor/Process || exit 1

CMD ["gunicorn","--bind","0.0.0.0:5000","--timeout","600","--workers","1","--threads","4","--access-logfile","-","--error-logfile","-","app:app"]
