# Python Server

This folder contains the Python startup service for the Spreadsheet Version History sample. It starts the included collaboration host, which provides real-time collaborative editing, Version History, preview, download, and restore functionality.

## Prerequisites

- Python 3
- Redis
- Valid Syncfusion license key

## Configure Redis

Update the Redis connection string in:

```text
collaboration-host/appsettings.json
```

Example:

```json
{
  "ConnectionStrings": {
    "Redis": "127.0.0.1:6379"
  }
}
```

## Configure the License

Set the Syncfusion license key in PowerShell:

```powershell
$env:SYNCFUSION_LICENSE_KEY = "YOUR_SYNCFUSION_LICENSE_KEY"
```

Register the Syncfusion JavaScript license key in:

```text
client/vue/src/main.ts
```

```ts
registerLicense('YOUR_SYNCFUSION_LICENSE_KEY');
```

Do not commit a license key to the repository.

## Configure the Client

In `client/vue/src/App.vue`, set the Python server URL:

```ts
const serviceUrl: string = 'http://127.0.0.1:5001/';
```

## Run the Server

Open PowerShell in the `server/python` directory:

```powershell
$env:SYNCFUSION_LICENSE_KEY = "YOUR_SYNCFUSION_LICENSE_KEY"
.\run.ps1
```

The server starts at:

```text
http://127.0.0.1:5001/
```

Verify the server:

```powershell
curl.exe http://127.0.0.1:5001/health
```

## Run the Client

Open another terminal:

```powershell
cd client\vue
npm install
npm run dev
```

Open the URL displayed in the terminal. To test collaboration, open the same room URL in multiple browser windows.
