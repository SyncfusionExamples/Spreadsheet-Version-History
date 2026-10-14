# Spreadsheet Collaborative Editing with Version History

This repository demonstrates real-time collaborative editing and Version History functionality in the Syncfusion Spreadsheet component.

The solution includes:

- Vue client application
- ASP.NET Core collaborative editing service
- Python collaborative editing service
- Redis-based synchronization
- Version History management
- Workbook restore and download support

---

## Repository Structure

```text
Spreadsheet-Version-History/
│
├── client/
│   └── Vue Spreadsheet application
│
├── server/
│   ├── aspnet-core/
│   │   └── ASP.NET Core collaborative editing service
│   │
│   └── python/
│       ├── Files/
│       ├── NETStandardWrapperLibrary/
│       ├── app.py
│       ├── appsettings.json
│       └── requirements.txt
│
├── license
└── README.md
```

---

## Components

### Client Application

Vue application hosting the Syncfusion Spreadsheet UI.

Location:

```text
client/
```

See:

```text
client/README.md
```

---

### ASP.NET Core Service

Collaborative editing backend built using ASP.NET Core.

Location:

```text
server/aspnet-core/
```

See:

```text
server/aspnet-core/README.md
```

---

### Python Service

Collaborative editing backend built using Python and a .NET Spreadsheet wrapper.

Location:

```text
server/python/
```

See:

```text
server/python/README.md
```

---

## Supported Features

### Collaborative Editing

- Real-time workbook synchronization
- Multi-user editing
- Selection synchronization
- Participant presence tracking
- Late-join synchronization

### Version History

- Automatic version creation
- Version listing
- Historical workbook preview
- Version download
- Restore previous versions

### Persistence

- Workbook save support
- Redis-backed action storage
- Session state management

---

## Typical Setup Flow

### Option 1: ASP.NET Core Backend

Start the ASP.NET Core service:

```text
server/aspnet-core
```

Then configure the Vue client to use the ASP.NET Core endpoint.

---

### Option 2: Python Backend

Build the .NET wrapper:

```text
server/python/NETStandardWrapperLibrary
```

Start the Python service:

```text
server/python
```

Then configure the Vue client to use the Python endpoint.

---

## License

This sample requires a valid Syncfusion license key.

For Syncfusion licensing information, visit:

https://www.syncfusion.com/sales/products