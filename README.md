# Spreadsheet Version History with Collaborative Editing

This proof of concept demonstrates how Spreadsheet Version History can work together with real-time collaborative editing. Each completed workbook action is stored as an immutable workbook snapshot, allowing users to preview, download, and restore earlier workbook states.

## Features

- Real-time collaborative Spreadsheet editing
- Automatic version creation for workbook actions
- Version History panel with date, participant, and action details
- Read-only historical version preview
- Download a copy of a selected version
- Restore a selected version as the current workbook
- Restore confirmation dialog
- Automatic refresh for all connected participants after restore
- Restore notification with an **Open Version History** option
- Late-joining participant synchronization
- Historical snapshot persistence independent of Redis operation cleanup

## Project Structure

```text
vue/
└── src/
    ├── App.vue
    ├── SpreadsheetEditorAdapter.ts
    └── style.css

server/
└── aspnet-core/
    ├── Controllers/
    │   └── CollaborativeEditingController.cs
    ├── Models/
    │   └── SpreadsheetVersionModels.cs
    ├── VersionData/
    ├── wwwroot/
    │   └── Files/
    │       └── Sample.xlsx
    └── appsettings.json
```

## Prerequisites

- Node.js and npm
- .NET 10 SDK
- Redis
- Syncfusion Spreadsheet packages
- Syncfusion Collaboration Client and Server packages
- Syncfusion XlsIO

## Redis Configuration

Add the Redis connection string to `server/aspnet-core/appsettings.json` using the configuration key expected by the Collaboration Server setup.

Example local Redis endpoint:

```json
{
    "RedisConnectionString": "localhost:6379"
}
```

The exact property name must match the server registration code.

Verify Redis before starting the server:

```bash
redis-cli ping
```

Expected response:

```text
PONG
```

## Install Vue Dependencies

Run from the Vue project directory:

```bash
npm install
npm install @syncfusion/ej2-vue-popups --save
```

The popup package is required for the restore confirmation and restore notification dialogs.

## Run the ASP.NET Core Server

```bash
cd server/aspnet-core
dotnet restore
dotnet build
dotnet run
```

The Vue application currently expects the server at:

```text
https://localhost:7002/
```

If the server uses another port, update `serviceUrl` in `App.vue`.

If the executable is locked by an older process, stop the process before rebuilding:

```bat
netstat -ano | findstr :7002
taskkill /PID <PID> /F
```

## Run the Vue Application

```bash
cd vue
npm install
npm run build
npm run dev
```

Open the URL displayed by Vite. The application creates a room ID in the query string:

```text
http://localhost:5173/?id=<room-name>
```

Share the same URL with other browser tabs or participants to join the same workbook session.

## Version Storage

Each collaboration room has a separate version directory:

```text
server/aspnet-core/VersionData/{roomName}/
```

The directory contains:

```text
Current.xlsx
versions.json
{versionId}.xlsx
```

- `Current.xlsx` is the current baseline after a restore.
- `versions.json` stores version metadata.
- `{versionId}.xlsx` is an immutable workbook snapshot for a historical version.

Version metadata includes:

```text
VersionId
FileName
ModifiedBy
CreatedAtUtc
CollaborationVersion
Action
```

## Automatic Version Creation

A version is created after the Collaboration Server assigns a version number to a workbook action.

```text
Spreadsheet action
    → UpdateAction
    → Collaboration Server assigns action version
    → Materialize workbook through that exact version
    → Save immutable XLSX snapshot
    → Add metadata to versions.json
    → Notify connected clients that history changed
```

A snapshot must include only actions through the target collaboration version:

```csharp
action.Version <= targetVersion
```

This prevents an older history entry from including actions that occurred later.

Selection and presence updates must not create workbook versions.

## Version History Preview

Opening Version History performs the following actions:

1. Opens the Version History panel.
2. Changes the Spreadsheet to read-only mode.
3. Continues refreshing the version metadata list.
4. Keeps the current workbook visible until a version is selected.

Selecting a version:

1. Sends the room name and version ID to `GetVersionWorkbook`.
2. Loads the selected immutable XLSX snapshot.
3. Opens the snapshot in the existing Spreadsheet.
4. Keeps the Spreadsheet read-only.
5. Displays **Download a copy** and **Restore** actions.

Historical preview is private to the current browser. Live actions from other participants must not modify the historical preview.

When the user selects **Back to document**, the application reloads the latest workbook from the server and resumes live collaboration.

## Restore Flow

```text
Participant selects a historical version
    → Restore confirmation dialog opens
    → Participant confirms restore
    → RestoreVersion copies the selected snapshot to Current.xlsx
    → Pending collaboration operations are cleared
    → Restore revision is incremented
    → Connected browsers detect the revision change
    → Every browser reloads the restored workbook
```

Only the participant initiating the restore sees the confirmation dialog.

Other connected participants receive a notification after the workbook reloads:

```text
Workbook restored to previous version
```

The notification provides:

- **Open Version History**
- **Close**

## Restore Revision Monitoring

A room restore revision is used as a reliable fallback because custom transport events may not always reach `applyRemoteAction()`.

The client periodically calls:

```text
GET /api/CollaborativeEditing/GetRestoreRevision/{roomName}
```

When the revision changes, the client reloads the current workbook and displays the restore notification.

The current in-memory restore revision store is suitable for a local proof of concept. A production implementation should store restore revision information in Redis or another shared persistent store.

## Participant Name Tracking

The participant name must be associated with the workbook action before automatic version metadata is created.

The client registers or includes the current participant name before sending the workbook action. The server then stores the name in `ModifiedBy`.

When testing participant names:

- Use a new room ID, or
- Delete the existing room folder under `VersionData`.

Existing metadata already stored as `Guest User` is immutable and will not update automatically.

## API Endpoints

### Import the latest workbook

```text
POST /api/CollaborativeEditing/ImportFile
```

### Submit a workbook action

```text
POST /api/CollaborativeEditing/UpdateAction
```

### Retrieve actions for synchronization

```text
POST /api/CollaborativeEditing/GetActionsFromServer
```

### Retrieve Version History

```text
GET /api/CollaborativeEditing/GetVersionHistory/{roomName}
```

### Retrieve a selected version

```text
POST /api/CollaborativeEditing/GetVersionWorkbook
```

### Download a selected version

```text
GET /api/CollaborativeEditing/DownloadVersion/{roomName}/{versionId}
```

### Restore a selected version

```text
POST /api/CollaborativeEditing/RestoreVersion
```

### Retrieve the restore revision

```text
GET /api/CollaborativeEditing/GetRestoreRevision/{roomName}
```

### Register the participant for an action

```text
POST /api/CollaborativeEditing/RegisterActionUser
```

Use this endpoint only when the Spreadsheet collaboration payload does not preserve a custom participant property.

## Redis Save Threshold and Historical Versions

Redis stores temporary collaboration operations for synchronization and operation transformation. When the configured save threshold is exceeded, older operations may be persisted into the source workbook and removed from Redis.

Historical versions remain restorable after Redis cleanup only when each version has already been saved as an immutable workbook snapshot in persistent storage.

```text
Redis operations
    → temporary collaboration state

VersionData/{roomName}/{versionId}.xlsx
    → permanent historical snapshot
```

Do not depend on Redis to reconstruct old historical versions after those operations have been cleared.

## Expected Multi-Browser Behavior

### Normal collaboration

```text
Browser 1 edits I1 = 1234
Browser 2 receives I1 = 1234
Browser 2 edits J1 = Hello
Browser 1 receives J1 = Hello
```

### Historical preview

```text
Browser 1 selects the first history entry
Browser 1 shows the older read-only snapshot
Browser 2 remains on the live workbook
Browser 2 can continue editing
Browser 1 historical preview does not receive live workbook actions
```

### Late joining

```text
Browser 3 joins the same room
Browser 3 loads the latest current workbook
```

### Restore

```text
Browser 2 restores an older version
Browser 2 reloads immediately
Browser 1 detects the restore revision
Browser 1 reloads the restored workbook
Browser 1 displays the restore notification
Browser 3 opened later loads the restored baseline
```

## Test Scenarios

1. Start Redis, ASP.NET Core, and Vue.
2. Open the same room in Browser 1 and Browser 2.
3. Edit `I1` in Browser 1.
4. Edit `J1` in Browser 2.
5. Confirm both live browsers contain both changes.
6. Open Version History.
7. Verify each workbook action has a history entry.
8. Select the older entry.
9. Confirm the older snapshot excludes the later action.
10. Confirm **Download a copy** and **Restore** appear.
11. Download the older and newer snapshots and confirm the files differ.
12. Keep Browser 1 in historical preview while Browser 2 edits the live workbook.
13. Confirm Browser 1 historical preview does not change.
14. Select **Back to document** and confirm Browser 1 reloads the latest workbook.
15. Restore an older version from Browser 2.
16. Confirm Browser 1 reloads automatically.
17. Confirm Browser 1 shows the restore notification.
18. Open Browser 3 and confirm the restored workbook is loaded.
19. Confirm new actions after restore synchronize normally.

## Troubleshooting

### Version History does not open

Ensure `SpreadsheetEditorAdapter` contains:

```ts
private isVersionHistoryMode: boolean = false;

public setVersionHistoryMode(enabled: boolean): void {
    this.isVersionHistoryMode = enabled;
}
```

Restart Vite and perform a hard refresh after replacing the adapter.

### `GetVersionWorkbook` returns HTTP 400

`RestoredBy` must be optional because preview and download requests do not send it:

```csharp
public string? RestoredBy { get; set; }
```

### A selected version still displays the latest workbook

Verify that the server:

- Saves a separate XLSX file for every version ID.
- Materializes only through the selected action version.
- Loads the snapshot through `GetVersionWorkbookPath(roomName, versionId)`.
- Returns `sfdt` using camelCase JSON.

Delete old incorrect snapshots before retesting.

### Download a copy and Restore are not visible

These actions appear only after the selected historical workbook opens successfully. Check the `GetVersionWorkbook` response and browser console.

### Version History shows `Guest User`

- Use a new room or delete old metadata.
- Verify the action-user registration request succeeds.
- Verify the server receives the participant name before creating the automatic version.
- Existing `Guest User` entries will not update automatically.

### Other browsers do not refresh after restore

Verify that:

- `RestoreVersion` increments the room restore revision.
- `GetRestoreRevision` returns camelCase JSON.
- Restore revision monitoring starts after joining the room.
- The polling timer is cleared only when the Vue component is destroyed.

### Server executable is locked

```bat
netstat -ano | findstr :7002
taskkill /PID <PID> /F
```

Then clean and rebuild:

```bat
rmdir /S /Q bin
rmdir /S /Q obj
dotnet restore
dotnet build
dotnet run
```

## POC Limitations

- A complete XLSX snapshot is created for each workbook action.
- File-system storage is intended only for local validation.
- Restore revision information is currently stored in memory.
- Version retention and cleanup policies are not implemented.
- Permissions and restore authorization are not implemented.
- Automatic snapshots may need action grouping or throttling for production.
- Production deployments should use shared durable storage and a distributed restore revision store.

## Production Recommendations

- Store snapshots in blob storage or another durable shared store.
- Store version metadata in a database.
- Store restore revisions in Redis or a database.
- Add version retention and cleanup policies.
- Add authorization for preview, download, and restore.
- Group rapid edits into logical versions instead of saving every low-level action.
- Add audit details for restore actions.
- Add conflict handling for simultaneous restore requests.

## Summary

This proof of concept separates temporary collaboration operations from permanent historical snapshots. Redis supports live synchronization, while immutable XLSX files provide durable Version History. A selected historical version is private and read-only. Restoring a version changes the room baseline, reloads all connected participants, and preserves the ability to preview and download earlier snapshots.
