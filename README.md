# Spreadsheet Collaborative Editing with Version History

This sample demonstrates real-time collaborative editing and Version History in the Syncfusion Vue Spreadsheet using a Python server and a .NET wrapper for Spreadsheet processing.

## Project Structure

```text
Spreadsheet-Version-History/
├── Files/
│   └── Data/
│       └── Sample.xlsx
├── frontend/
│   ├── public/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── NETStandardWrapperLibrary/
│   └── WebServiceLibrary/
│       ├── SpreadsheetEditor.cs
│       ├── WebServiceLibrary.csproj
│       ├── WebServiceLibrary.sln
│       └── build.ps1
├── app.py
├── appsettings.json
├── requirements.txt
└── README.md
```

## Prerequisites

- Python 3.8 or later
- .NET 10 SDK
- Node.js and npm
- Redis connection
- Valid Syncfusion license key

## Build the .NET Wrapper

Navigate to the wrapper project:

```powershell
cd NETStandardWrapperLibrary\WebServiceLibrary
```

Build and publish the wrapper:

```powershell
dotnet restore
dotnet build -c Release
dotnet publish -c Release
```

Return to the project root:

```powershell
cd ..\..
```

## Install Python Dependencies

```powershell
python -m pip install -r requirements.txt
```

## Configure Redis

Update the Redis settings in `appsettings.json`:

```json
{
  "Redis": {
    "Host": "YOUR_REDIS_HOST",
    "Port": 6380,
    "Password": "YOUR_REDIS_ACCESS_KEY",
    "Ssl": true,
    "AbortConnect": false
  }
}
```

## Configure the Syncfusion License

Open `app.py` and replace the placeholder in the following line with a valid Syncfusion license key:

```python
LICENSE_KEY = os.environ.get(
    "SYNCFUSION_LICENSE_KEY",
    "YOUR_SYNCFUSION_LICENSE_KEY"
).strip()
```

Do not commit the actual license key to a public repository.

## Run the Python Server

From the project root, run:

```powershell
python app.py
```

The server starts at:

```text
http://127.0.0.1:5000/
```

## Configure and Run the Vue Application

In `frontend/src/App.vue`, set the service URL:

```ts
const serviceUrl: string = 'http://127.0.0.1:5000/';
```

Open another terminal and run:

```powershell
cd frontend
npm install
npm run dev
```

Open the URL displayed in the terminal. Use the same room URL in multiple browser windows to test collaborative editing and Version History.

## Supported Features

- Real-time collaborative Spreadsheet editing
- Participant presence and selection synchronization
- Late-join synchronization
- Automatic Version History creation
- Historical workbook preview
- Version download
- Version restore and connected-user synchronization
