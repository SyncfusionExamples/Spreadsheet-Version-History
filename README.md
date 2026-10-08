# Spreadsheet Version History

This sample demonstrates Version History with real-time collaborative editing in the Syncfusion® Spreadsheet Editor. Users can preview, download, and restore previous workbook versions while multiple participants edit the same workbook.

## Features

- Real-time collaborative editing
- Automatic workbook version creation
- Read-only preview of previous versions
- Download and restore support
- Restore notifications for connected participants
- Late-join synchronization
- Redis integration

## Project Structure

```text
├── client/
├── server/
└── README.md
```

Platform-specific implementations and setup instructions are available in the README file inside each client and server directory.

## Prerequisites

- .NET 10.0 SDK
- Node.js and npm
- Redis server
- Syncfusion license key

## Setup

1. Configure the Redis connection string in the server configuration.
2. Register the Syncfusion license key.
3. Install the dependencies defined by the selected client and server projects.
4. Start the server application.
5. Start the selected client application.
6. Share the same application URL with other participants to join the same workbook session.

Refer to the README file inside the selected project directory for platform-specific commands and configuration.

## Version History Flow

```text
Workbook action
    → Automatic XLSX snapshot
    → Version History
    → Preview, download, or restore
```

Historical previews are read-only and private to the browser that selected them. Restoring a version updates the current workbook for all connected participants.

## Version Storage

Snapshots are stored by collaboration room:

```text
server/aspnet-core/VersionData/{roomName}/
```

Each version is stored as an immutable XLSX file, so versions remain available even after older collaboration operations are removed from Redis.

## Testing

1. Open the same room in two browsers/tabs.
2. Edit different cells in each browser.
3. Open Version History and preview previous versions.
4. Download or restore a selected version.
5. Verify that all connected browsers reload after restore.
6. Open another browser and verify late-join synchronization.
