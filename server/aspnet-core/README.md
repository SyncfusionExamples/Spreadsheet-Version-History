# ASP.NET Core Spreadsheet Collaboration Server

This project provides the ASP.NET Core Collaboration Server for real-time collaborative editing in the Syncfusion® Spreadsheet. It uses SignalR for real-time communication and Redis to maintain collaboration operations and room state.

## Prerequisites

Before running the server, ensure that the following are available:

- .NET 10.0 SDK
- Redis Server or a hosted Redis service
- The `wwwroot/Files/Sample.xlsx` workbook

## Configure the Redis connection

Open `appsettings.json` and replace the Redis connection-string placeholder:

```json
{
  "ConnectionStrings": {
    "Redis": "Your_Connection_string"
  }
}
```

For a local Redis instance, the value can be similar to:

```json
{
  "ConnectionStrings": {
    "Redis": "localhost:6379"
  }
}
```

## Register the Syncfusion license key

The server reads the Syncfusion license key from either a local license file or an environment variable.

### Option 1: License file

Create a `SyncfusionLicense.txt` file in the project root and add the license key as its content.

```text
YOUR_SYNCFUSION_LICENSE_KEY
```

### Option 2: Environment variable

Set the `SYNCFUSION_LICENSE_KEY` environment variable before running the server.

Windows Command Prompt:

```cmd
set SYNCFUSION_LICENSE_KEY=YOUR_SYNCFUSION_LICENSE_KEY
```

Windows PowerShell:

```powershell
$env:SYNCFUSION_LICENSE_KEY="YOUR_SYNCFUSION_LICENSE_KEY"
```

Linux or macOS:

```bash
export SYNCFUSION_LICENSE_KEY=YOUR_SYNCFUSION_LICENSE_KEY
```

## Source workbook

The collaboration sample loads the source workbook from:

```text
wwwroot/Files/Sample.xlsx
```

Ensure that `Sample.xlsx` exists at this location before starting the server.

## Run the server

Navigate to the ASP.NET Core server folder:

```bash
cd server/aspnet-core
```

Restore the required packages:

```bash
dotnet restore
```

Run the server:

```bash
dotnet run
```

The development profile uses the following URLs:

```text
https://localhost:7002
http://localhost:5209
```

Use one of these URLs as the Collaboration Server URL in the client applications.

For example:

```ts
const serviceUrl: string = 'https://localhost:7002/';
```

## Collaboration endpoints

The server exposes the following Spreadsheet collaboration endpoints under:

```text
api/CollaborativeEditing
```

- `POST /ImportFile` loads the source workbook, applies pending room operations, and returns the synchronized workbook and version.
- `POST /UpdateAction` stores and broadcasts a Spreadsheet action.
- `POST /UpdateSelection` updates and broadcasts a participant's selection.
- `GET /GetRoomSelections/{roomName}` returns the active selections for a collaboration room.
- `POST /RemoveUserSelection` removes a disconnected participant's selection.
- `POST /GetActionsFromServer` returns actions newer than the client's last synchronized version.

The collaboration transport endpoint is registered through `MapCollaborationServer` and uses SignalR.

## Spreadsheet endpoints

The server also provides the following standard Spreadsheet endpoints:

```text
POST /api/Spreadsheet/Open
POST /api/Spreadsheet/Save
```

These endpoints support opening and saving Spreadsheet files.

## CORS

The server uses the `AllowAllOrigins` CORS policy so that the client samples can access the collaboration and Spreadsheet endpoints during development.

## Test collaborative editing

1. Start Redis.
2. Run the ASP.NET Core server using `dotnet run`.
3. Configure a client sample with the displayed server URL.
4. Start the client application.
5. Open the complete client URL, including the `id` query parameter, in two browser tabs or windows.
6. Edit a cell and verify that the supported change is synchronized between both clients.

## Project structure

```text
server/aspnet-core/
|-- Adapters/
|   `-- SpreadsheetCollaborativeAdaptor.cs
|-- Controllers/
|   |-- CollaborativeEditingController.cs
|   |-- SpreadsheetController.cs
|   `-- TestController.cs
|-- Properties/
|   `-- launchSettings.json
|-- wwwroot/
|   `-- Files/
|       `-- Sample.xlsx
|-- appsettings.Development.json
|-- appsettings.json
|-- ej2-spreadsheet-server.csproj
|-- ej2-spreadsheet-server.sln
|-- NuGet.Config
|-- Program.cs
|-- SyncfusionLicense.txt
|-- web.config
`-- README.md
```

## Troubleshooting

### Redis connection failure

Verify that Redis is running and that the `Redis` value in `appsettings.json` contains a valid connection string.

### Workbook does not load

Verify that the following file exists:

```text
wwwroot/Files/Sample.xlsx
```

Also confirm that the browser Network panel does not show an error for:

```text
api/CollaborativeEditing/ImportFile
```

### Client cannot connect to the collaboration room

Verify that:

- The ASP.NET Core server is running.
- The client uses the correct server URL.
- The client and server use SignalR.
- The browser accepts the local HTTPS development certificate.
- The browser console does not contain SignalR or network errors.

### Syncfusion license warning

Ensure that a valid license key is available through `SyncfusionLicense.txt` or the `SYNCFUSION_LICENSE_KEY` environment variable.

### Package restore failure

Confirm that the package sources configured in `NuGet.Config` are accessible, and then run:

```bash
dotnet restore
```

## License

This project is licensed under the terms specified in the repository's license file. Syncfusion® packages are subject to the applicable Syncfusion license terms.
