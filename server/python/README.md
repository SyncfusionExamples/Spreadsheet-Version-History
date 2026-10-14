# Python Collaborative Editing Service

This project provides real-time collaborative editing and Version History support for the Syncfusion Spreadsheet using Python, Redis, and a .NET Spreadsheet processing wrapper.

## Project Structure

```text
python/
│
├── Files/
│   ├── Data/
│   │   └── Sample.xlsx
│   └── Output/
│
├── NETStandardWrapperLibrary/
│   └── WebServiceLibrary/
│
├── app.py
├── appsettings.json
├── requirements.txt
├── Dockerfile
└── README.md
```

## Prerequisites

Before running the service, ensure the following software is installed:

- Python 3.8 or later
- .NET 10 SDK
- Redis
- Valid Syncfusion License Key

---

## Build the .NET Wrapper

The Python service relies on a .NET wrapper for Spreadsheet operations such as:

- Opening workbooks
- Applying collaborative actions
- Saving workbooks
- Version History processing
- Workbook restoration

Navigate to the wrapper project:

```powershell
cd NETStandardWrapperLibrary\WebServiceLibrary
```

Restore packages:

```powershell
dotnet restore
```

Build the project:

```powershell
dotnet build -c Release
```

Publish the project:

```powershell
dotnet publish -c Release
```

Return to the Python project root:

```powershell
cd ..\..
```

---

## Install Python Dependencies

Install all required packages:

```powershell
pip install -r requirements.txt
```

---

## Configure Redis

Open:

```text
appsettings.json
```

Update the Redis configuration:

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

---

## Configure the Syncfusion License

Open:

```text
app.py
```

Replace the placeholder license key:

```python
LICENSE_KEY = os.environ.get(
    "SYNCFUSION_LICENSE_KEY",
    "YOUR_SYNCFUSION_LICENSE_KEY"
).strip()
```

Alternatively, configure the license key as an environment variable:

```powershell
set SYNCFUSION_LICENSE_KEY=YOUR_LICENSE_KEY
```

---

## Run the Service

From the Python project root:

```powershell
python app.py
```

The service starts at:

```text
http://127.0.0.1:5000/
```

---

## Workbook Storage

### Input Files

Place source workbooks in:

```text
Files/Data/
```

Example:

```text
Files/Data/Sample.xlsx
```

### Saved Workbooks

Modified workbooks are saved to:

```text
Files/Output/
```

If a workbook does not exist in the Output folder, the service uses the workbook from the Data folder as the source workbook.

---

## Supported Features

### Collaborative Editing

- Real-time action synchronization
- Multi-user editing
- Participant synchronization
- Selection synchronization
- Late-join synchronization

### Persistence

- Redis-based action storage
- Workbook save support
- Session state management

### Version History

- Automatic version creation
- Version listing
- Historical workbook preview
- Version download
- Restore previous versions

---

## API Endpoints

The service exposes endpoints used by the Syncfusion Spreadsheet for:

- Import Workbook
- Collaborative Editing
- Save Workbook
- Version History
- Restore Version

These endpoints are automatically consumed by the Vue client application.

---

## Troubleshooting

### Redis Connection Issues

Verify:

- Redis server is running
- Host name is correct
- Port is accessible
- Password is valid
- SSL settings match the Redis configuration

### Wrapper Not Found

Rebuild and publish the .NET wrapper:

```powershell
dotnet restore
dotnet build -c Release
dotnet publish -c Release
```

### Workbook Save Failures

Verify:

- Workbook exists in `Files/Data`
- Output folder has write permissions
- Wrapper publish output is available
- Workbook is not locked by another process
