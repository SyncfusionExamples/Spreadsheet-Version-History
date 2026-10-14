from flask import Flask, request, Response, send_file, send_from_directory
import json
import json as json_lib
from flask_cors import CORS #import CORS from flask_cors
from flask_sock import Sock

import os
import os as _os  # alias used by the settings loader further down
import sys as _sys
import traceback
import uuid
import datetime
from io import BytesIO

# ============================================================================
# Pythonnet / .NET runtime bootstrap (MUST run before `import clr`).
# ----------------------------------------------------------------------------
# pythonnet only honours PYTHONNET_RUNTIME at module-import time, so we
# set it before the first clr import. We also pin DOTNET_ROOT (in case
# the dev box has no `dotnet` on PATH, e.g. a Windows service install)
# and DOTNET_ROLL_FORWARD=LatestMajor so the wrapper (built for net10.0)
# will load even when a newer runtime is installed (the host picks the
# highest matching version that's >= 10.0).
# ============================================================================
_os.environ.setdefault("PYTHONNET_RUNTIME", "coreclr")
if not _os.environ.get("DOTNET_ROOT"):
    # Best-effort: pick the newest installed Microsoft.NETCore.App.
    _candidate = None
    for _base in (
        r"C:\Program Files\dotnet",
        "/usr/share/dotnet",
        "/usr/local/share/dotnet",
        "/usr/lib/dotnet",
    ):
        if os.path.isdir(os.path.join(_base, "host", "fxr")):
            _candidate = _base
            break
    if _candidate:
        _os.environ["DOTNET_ROOT"] = _candidate
_os.environ.setdefault("DOTNET_ROLL_FORWARD", "LatestMajor")

# Pre-configure LD_LIBRARY_PATH on Linux for native library discovery (especially SkiaSharp)
# This MUST run before CLR initialization to ensure native libraries are found when the runtime
# loads managed assemblies that depend on native .so files (libSkiaSharp.so, libgdiplus, etc.)
if _sys.platform.startswith("linux"):
    # System graphics libraries that SkiaSharp and other rendering libraries depend on
    base_ld_paths = "/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu"
    existing_ld = _os.environ.get("LD_LIBRARY_PATH", "").strip()
    if existing_ld:
        new_ld = base_ld_paths + ":" + existing_ld
    else:
        new_ld = base_ld_paths
    _os.environ["LD_LIBRARY_PATH"] = new_ld
    print(f"[app] Pre-configured LD_LIBRARY_PATH for Linux: {new_ld[:120]}...", flush=True)

# Import clr AFTER the env-var setup above.
import clr  # noqa: E402  (must come after PYTHONNET_RUNTIME setup)

app = Flask(
__name__,
static_folder='frontend/dist',
static_url_path=''
)

sock = Sock(app)

# ---- Minimal CORS + large-file support ----
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 # 500 MB
app.config['MAX_FORM_MEMORY_SIZE'] = 500 * 1024 * 1024 # 500 MB

# ============================================================================
# Sub-path support for SPA routing (e.g., load balancer path remapping)
# ============================================================================
# When deployed behind a load balancer with path mapping, the application
# can still be accessed at both the root path (/) and a sub-path. This is
# controlled via the BASE_PATH environment variable.
# ============================================================================
BASE_PATH = os.environ.get('BASE_PATH', '').rstrip('/')

print(f"[app] BASE_PATH for sub-path routing: '{BASE_PATH}' (empty = root only)", flush=True)

# ============================================================================
# Collaboration WebSocket Storage
# ============================================================================

sessions = {}

rooms = {}

# ============================================================================
# Selection Storage
# ============================================================================

room_selections = {}

CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=False,
    expose_headers=["Content-Disposition", "Content-Length", "Content-Type"],
)

# Force CORS headers on EVERY response (including 413/500 errors)
@app.after_request
def add_cors_on_errors(resp):
    resp.headers["Access-Control-Allow-Origin"]  = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp
# -------------------------------------------

# ============================================================================
# Filesystem layout
# ----------------------------------------------------------------------------
#   <cwd>/NETStandardWrapperLibrary/WebServiceLibrary/bin/Release/net10.0/publish/
#       Compiled .NET wrappers (Spreadsheet).
# ============================================================================
current_working_directory = os.getcwd()

# Try multiple possible publish locations, in order of preference:
#   1. net10.0/publish/           (preferred — matches our target framework)
#   2. net10.0/linux-x64/publish/ (Linux RID-specific)
#   3. Last resort: use candidate_a even if it doesn't exist yet
_publish_candidate_a = os.path.join(
    current_working_directory,
    "NETStandardWrapperLibrary/WebServiceLibrary/bin/Release/net10.0/publish/"
)
_publish_candidate_b = os.path.join(
    current_working_directory,
    "NETStandardWrapperLibrary/WebServiceLibrary/bin/Release/net10.0/linux-x64/publish/"
)

# Use the first candidate that exists
publish_base = None
for candidate in [_publish_candidate_a, _publish_candidate_b]:
    if os.path.isdir(candidate):
        publish_base = candidate
        break

if not publish_base:
    # Last resort: use candidate_a even if it doesn't exist yet
    publish_base = _publish_candidate_a

print(f"[app] Using publish base: {publish_base}", flush=True)

files_root = os.path.join(current_working_directory, "Files")

# Make sure the Files directory exists (idempotent).
os.makedirs(files_root, exist_ok=True)

# ============================================================================
# Load the .NET wrapper assemblies via pythonnet.
# ----------------------------------------------------------------------------
# We add the publish folder to sys.path so pythonnet can locate
# every DLL by simple name. The .NET BCL types (System.Buffers,
# System.Memory, Microsoft.Bcl.AsyncInterfaces, System.Text.Json, etc.)
# are resolved automatically by the .NET host — we don't need to
# AddReference them explicitly.
# ============================================================================
# Native runtimes may be placed in either of these locations, depending on
# how `dotnet publish` was invoked:
#   1) <publishBase>/runtimes/linux-x64/native/   (default NuGet layout)
#   2) <publishBase>/runtimes/win-x64/native/     (default NuGet layout for Windows)
#   3) <publishBase>/                              (when the publish RID
#                                                   matches the container RID
#                                                   and NuGet flattens the layout)
# Check all locations, and also always include <publishBase> itself since the .so files
# need to be on LD_LIBRARY_PATH (Linux) or PATH (Windows) for the .NET runtime's 
# dlopen()/LoadLibrary() to succeed.
# ============================================================================
runtimes_base = os.path.join(publish_base, "runtimes")

native_search_dirs = []
if _sys.platform.startswith("win"):
    # Windows: Check win-x64/native and root
    native_search_dirs = [
        os.path.join(runtimes_base, "win-x64", "native"),
        publish_base,
    ]
elif _sys.platform.startswith("linux"):
    # Linux: Check linux-x64/native and root
    native_search_dirs = [
        os.path.join(runtimes_base, "linux-x64", "native"),
        publish_base,
    ]

# Add all found native directories to PATH (Windows) or LD_LIBRARY_PATH (Linux)
# IMPORTANT: Build the full LD_LIBRARY_PATH BEFORE the loop to avoid overwriting
if _sys.platform.startswith("linux"):
    # Collect all native directories that exist
    found_native_dirs = []
    for native_dir in native_search_dirs:
        if os.path.isdir(native_dir):
            found_native_dirs.append(native_dir)
    
    # System graphics libraries — MUST include these for SkiaSharp to work
    base_ld_paths = "/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu"
    
    # Build complete LD_LIBRARY_PATH: native dirs + system libs + existing value
    ld_parts = found_native_dirs + [base_ld_paths]
    existing_ld = os.environ.get("LD_LIBRARY_PATH", "").strip()
    if existing_ld:
        ld_parts.append(existing_ld)
    
    new_ld = ":".join(ld_parts)
    os.environ["LD_LIBRARY_PATH"] = new_ld
    
    print(f"[app] Configured LD_LIBRARY_PATH for Linux graphics libraries", flush=True)
    for native_dir in found_native_dirs:
        print(f"[app]   - Added: {native_dir}", flush=True)
    print(f"[app]   - Added system graphics paths", flush=True)
    print(f"[app] Full LD_LIBRARY_PATH: {new_ld[:100]}...", flush=True)

elif _sys.platform.startswith("win"):
    # Windows: Add native directories to PATH
    for native_dir in native_search_dirs:
        if os.path.isdir(native_dir):
            os.environ["PATH"] = native_dir + os.pathsep + os.environ.get("PATH", "")
            print(f"[app] Added Windows native path: {native_dir}", flush=True)

_sys.path.insert(0, publish_base)
print(f"[app] Added publish base to sys.path: {publish_base}", flush=True)

_ASSEMBLY_NAMES = [
    "Syncfusion.EJ2.Spreadsheet",
    "BitMiracle.LibTiff.NET",
    "HarfBuzzSharp",
    "Newtonsoft.Json",
    "SkiaSharp",
    "SkiaSharp.HarfBuzz",
    "Syncfusion.Compression.Portable",
    "Syncfusion.Licensing",
    "Syncfusion.MetafileRenderer.Portable",
    "Syncfusion.OfficeChart.Portable",
    "Syncfusion.Pdf.Imaging.Portable",
    "Syncfusion.Pdf.Portable",
    "Syncfusion.SkiaSharpHelper.Portable",
    "Syncfusion.XlsIO.Portable",
    "Syncfusion.XlsIORenderer.Portable",
    # Syncfusion's EJ2 Spreadsheet does a literal Assembly.Load on the
    # ASP.NET Core 2.3 Mvc facade. These come from the .csproj's
    # PackageReference entries and are published into the same folder
    # by `dotnet publish` — load them before WebServiceLibrary so the
    # SpreadsheetEditor's Save() path resolves them.
    "Microsoft.AspNetCore.Mvc.Core",
    "Microsoft.AspNetCore.Mvc.Abstractions",
    "WebServiceLibrary",
]

for _name in _ASSEMBLY_NAMES:
    try:
        clr.AddReference(_name)
        print(f"[app] [OK] Loaded {_name}", flush=True)
    except Exception as e:
        print(f"[app] [ERR] Failed to load {_name}: {e}", flush=True)
        # Critical assemblies for spreadsheet functionality — fail fast
        if _name in ("SkiaSharp", "Syncfusion.XlsIO.Portable", "Syncfusion.Pdf.Portable"):
            print(f"[app] FATAL: {_name} is required for spreadsheet functionality!", flush=True)
            raise

# ============================================================================
# Python-side imports from the C# wrapper namespace.
# ============================================================================
from WebServiceLibrary import SpreadsheetEditor
from Syncfusion.EJ2.Spreadsheet import SaveSettings, SaveType
from Syncfusion.Licensing import SyncfusionLicenseProvider
from System import Enum
from System.IO import SeekOrigin

# ---------------------------------------------------------------------------
# Register the Syncfusion license
LICENSE_KEY = _os.environ.get("SYNCFUSION_LICENSE_KEY", "")
SyncfusionLicenseProvider.RegisterLicense(LICENSE_KEY)

# ---------------------------------------------------------------------------
# Configuration
# ----------
#
#     appsettings.json              — base settings (committed to git, OK to leave empty)
#     appsettings.Development.json  — dev secrets (recommended: gitignored)
# ---------------------------------------------------------------------------
def _deep_merge(base, overlay):
    """Recursively merge `overlay` into `base`.

    Rules:
      * Nested dicts are merged key-by-key.
      * Empty / None values in the overlay are ignored (they don't
        clobber a real value in the base).
      * Non-empty scalars from the overlay replace the base value.
    """
    if isinstance(base, dict) and isinstance(overlay, dict):
        for k, v in overlay.items():
            if v is None or v == "":
                # Empty overlay value: keep the base.
                continue
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                base[k] = _deep_merge(base[k], v)
            else:
                base[k] = v
    return base

def _load_settings():
    settings = {}
    base = os.path.join(current_working_directory, "appsettings.json")
    dev  = os.path.join(current_working_directory, "appsettings.Development.json")
    for path in (base, dev):
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    settings = _deep_merge(settings, json_lib.load(f))
            except Exception as e:
                print(f"[app] warning: failed to read {path}: {e}", flush=True)
    return settings

_settings = _load_settings()

spreadEditor = SpreadsheetEditor()   # Spreadsheet wrapper

# Validate that editor initialized correctly
try:
    if not hasattr(spreadEditor, 'Open'):
        raise AttributeError("SpreadsheetEditor missing Open method")
    print("[app] [OK] SpreadsheetEditor initialized successfully", flush=True)
except Exception as e:
    print(f"[app] [ERR] Editor initialization failed: {e}", flush=True)
    raise

def send_message(ws, action, payload):

    message = {
        "event": action,
        "data": payload
    }

    print(
        f"[WS SEND] {json.dumps(message)}"
    )

    ws.send(json.dumps(message))


def broadcast_to_room(
    room_name,
    action,
    payload,
    exclude_connection=None
):

    if room_name not in rooms:
        return

    dead_connections = []

    for connection_id in rooms[room_name]:

        if connection_id == exclude_connection:
            continue

        try:

            session = sessions.get(connection_id)

            if session:
                send_message(
                    session["socket"],
                    action,
                    payload
                )

        except Exception:
            dead_connections.append(
                connection_id
            )

    for connection_id in dead_connections:

        sessions.pop(
            connection_id,
            None
        )

        rooms[room_name].discard(
            connection_id
        )


@sock.route('/ws')
def collaboration(ws):

    connection_id = str(uuid.uuid4())

    sessions[connection_id] = {
        "socket": ws,
        "roomName": None,
        "currentUser": None
    }

    print(f"[WS] Connected: {connection_id}")

    send_message(
        ws,
        "connectionId",
        connection_id
    )

    try:

        while True:

            raw = ws.receive()

            if raw is None:
                break

            print(f"[WS] RAW: {raw}")

            try:
                message = json.loads(raw)
            except Exception as ex:
                print(f"[WS] Invalid JSON: {ex}")
                continue

            event_name = (
                message.get("event")
                or message.get("type")
            )

            if not event_name:
                continue

            # =================================================
            # JoinGroup / join
            # =================================================

            if event_name in ["JoinGroup", "join"]:

                room_name = (
                    message.get("roomName")
                    or message.get("data", {}).get("roomName")
                )

                current_user = (
                    message.get("currentUser")
                    or message.get("data", {}).get("currentUser")
                )

                if not room_name:
                    continue

                sessions[connection_id]["roomName"] = room_name
                sessions[connection_id]["currentUser"] = current_user

                rooms.setdefault(room_name, set())
                rooms[room_name].add(connection_id)
                print(
                    f"[WS] Room={room_name}, "
                    f"Users={len(rooms[room_name])}"
                )

                print(
                    f"[WS] User '{current_user}' joined room '{room_name}'"
                )

                # Get existing users

                existing_users = []
                for conn_id in rooms[room_name]:

                    if conn_id == connection_id:
                        continue

                    existing_users.append({
                        "connectionId": conn_id,
                        "currentUser": sessions[conn_id].get("currentUser"),
                        "roomName": room_name
                    })
                # Send existing users to new participant
                if existing_users:

                    send_message(
                        ws,
                        "addUser",
                        existing_users
                    )
                # Notify other users
                user_info = {
                    "connectionId": connection_id,
                    "currentUser": current_user,
                    "roomName": room_name
                }

                broadcast_to_room(
                    room_name,
                    "addUser",
                    user_info,
                    exclude_connection=connection_id
                )

            # =================================================
            # Spreadsheet Action
            # =================================================

            elif event_name == "action":

                action_data = (
                    message.get("data")
                    or message
                )

                room_name = action_data.get("roomName")

                if not room_name:
                    continue

                print(
                    f"[WS] Action received for room '{room_name}'"
                )

                # Initial POC:
                # Just rebroadcast action to room.

                broadcast_to_room(
                    room_name,
                    "action",
                    action_data
                )

            # =================================================
            # Leave Room
            # =============

            elif event_name == "leave":

                print(
                    f"[WS] Leave received from {connection_id}"
                )

                break

            # =================================================
            # Ping
            # =================================================

            elif event_name == "ping":

                send_message(
                    ws,
                    "pong",
                    None
                )

    except Exception as ex:

        print(
            f"[WS] Error: {str(ex)}"
        )

    finally:

        print(
            f"[WS] Disconnecting: {connection_id}"
        )

        session = sessions.get(connection_id)

        if session:

            room_name = session.get("roomName")

            if room_name and room_name in rooms:

                rooms[room_name].discard(
                    connection_id
                )

                # Notify remaining users

                broadcast_to_room(
                    room_name,
                    "removeUser",
                    connection_id
                )

                # Cleanup empty room

                if len(rooms[room_name]) == 0:
                    del rooms[room_name]

            sessions.pop(
                connection_id,
                None
            )

        print(
            f"[WS] Disconnected: {connection_id}"
        )

# ============================================================================
# ---- Spreadsheet endpoints (existing — unchanged) -------------------------
# ============================================================================

@app.route('/Open', methods=['POST'])
@app.route(f'{BASE_PATH}/Open', methods=['POST'])
def openExcel():
    if 'file' in request.files:
        files = request.files['file']
        # Get the stream data
        print(files)
        stream_data = files.stream.read()
        # Calling our Open method from our SpreadsheetEditor class which will return the Workbook JSON string
        return spreadEditor.Open(stream_data)
    else:
        return ""

@app.route('/Save', methods=['POST'])
@app.route(f'{BASE_PATH}/Save', methods=['POST'])
def saveExcel():
    try:
        # Extract parameters from form data
        json_data = request.form.get('JSONData', '')
        save_type = request.form.get('saveType', 'Xlsx')  # Default to Xlsx
        file_name = request.form.get('fileName', 'Sample')

        # Extract PDF layout settings if provided
        pdf_layout_settings = request.form.get('pdfLayoutSettings', '{}')

        # Create SaveSettings object
        save_settings = SaveSettings()
        save_settings.JSONData = json_data
        # Convert string to SaveType enum
        save_settings.SaveType = Enum.Parse(SaveType, save_type)
        save_settings.FileName = file_name
        save_settings.PdfLayoutSettings = pdf_layout_settings

        # Call the Save method from SpreadsheetEditor class
        file_stream = spreadEditor.Save(save_settings)

        # Convert .NET MemoryStream to bytes
        file_stream.Seek(0, SeekOrigin.Begin)  # Seek to beginning
        stream_bytes = file_stream.ToArray()  # Convert to byte array
        file_stream.Dispose()  # Clean up the stream

        # Convert bytes to BytesIO for Flask
        output = BytesIO(stream_bytes)
        output.seek(0)

        extension = f".{save_type.lower()}"
        # Get the mime type based on the save type.
        mime_type = {
            "xls":  "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "pdf": "application/pdf",
            "csv": "text/csv"
        }.get(save_type.lower(), "application/octet-stream")

        return send_file(
            output,
            as_attachment=True,
            download_name=f"{file_name}{extension}",
            mimetype=mime_type
        )

    except Exception as e:
        import traceback
        error_msg = f"Error saving file: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return error_msg, 500


@app.route(
    "/api/CollaborativeEditing/ImportFile",
    methods=["POST"]
)
@app.route(
    f"{BASE_PATH}/api/CollaborativeEditing/ImportFile",
    methods=["POST"]
)
def import_file():

    try:

        request_data = request.get_json() or {}

        file_name = (
            request_data.get("fileName")
            or "Sample.xlsx"
        )

        room_name = (
            request_data.get("roomName")
            or "default"
        )

        print(
            f"[COLLAB] ImportFile "
            f"File={file_name}, "
            f"Room={room_name}"
        )

        # Safe filename resolution
        safe_name = os.path.basename(file_name)
        
        # Append .xlsx if no extension
        if not safe_name.endswith(('.xlsx', '.xls', '.csv')):
            safe_name = f"{safe_name}.xlsx"
        
        workbook_path = os.path.join(
            files_root,
            safe_name
        )

        if not os.path.exists(workbook_path):
            error_payload = json.dumps({
                "error": f"Workbook not found: {safe_name}"
            })
            return Response(
                error_payload,
                status=404,
                mimetype="application/json"
            )

        with open(workbook_path, "rb") as file:
            workbook_bytes = file.read()

        sfdt = spreadEditor.Open(workbook_bytes)

        response = {
            "version": 0,
            "sfdt": sfdt
        }

        return Response(
            json.dumps(response),
            mimetype="application/json"
        )

    except Exception as ex:

        print(
            f"[COLLAB] ImportFile Error: "
            f"{str(ex)}"
        )

        return Response(
            json.dumps({
                "error": str(ex)
            }),
            status=500,
            mimetype="application/json"
        )

@app.route(
    "/api/CollaborativeEditing/UpdateAction",
    methods=["POST"]
)
@app.route(
    f"{BASE_PATH}/api/CollaborativeEditing/UpdateAction",
    methods=["POST"]
)
def update_action():

    try:

        data = request.get_json()

        print(
            "[COLLAB] UpdateAction:",
            json.dumps(data, indent=2)
        )

        if not data:
            return Response(
                json.dumps({}),
                mimetype="application/json"
            )

        room_name = data.get("roomName")

        if not room_name:
            return Response(
                json.dumps(data),
                mimetype="application/json"
            )

        # POC versioning
        data["version"] = data.get("version", 0) + 1

        # Broadcast to all other users in room
        connection_id = data.get("connectionId")

        broadcast_to_room(
            room_name,
            "action",
            data,
            exclude_connection=connection_id
        )

        print(
            f"[COLLAB] Action broadcasted to room {room_name}"
        )

        return Response(
            json.dumps(data),
            mimetype="application/json"
        )

    except Exception as ex:

        print(
            f"[COLLAB] UpdateAction Error: {ex}"
        )

        return Response(
            json.dumps({
                "error": str(ex)
            }),
            status=500,
            mimetype="application/json"
        )

@app.route(
    "/api/CollaborativeEditing/UpdateSelection",
    methods=["POST"]
)
@app.route(
    f"{BASE_PATH}/api/CollaborativeEditing/UpdateSelection",
    methods=["POST"]
)
def update_selection():

    try:
        data = request.get_json()
        print(
            "[COLLAB] UpdateSelection:",
            json.dumps(data, indent=2)
        )
        if not data:
            return Response(
                json.dumps({}),
                mimetype="application/json"
            )
        room_name = data.get("roomName")
        connection_id = data.get("connectionId")
        if (
            not room_name or
            not connection_id
        ):
            return Response(
                json.dumps(data),
                mimetype="application/json"
            )
        # Store latest selection per user
        room_selections.setdefault(
            room_name,
            {}
        )
        room_selections[room_name][connection_id] = data
        # Broadcast to everyone except sender
        broadcast_to_room(
            room_name,
            "action",
            data,
            exclude_connection=connection_id
        )

        print(
            f"[COLLAB] Selection broadcasted to room {room_name}"
        )

        return Response(
            json.dumps(data),
            mimetype="application/json"
        )

    except Exception as ex:

        print(
            f"[COLLAB] UpdateSelection Error: {ex}"
        )

        return Response(
            json.dumps({
                "error": str(ex)
            }),
            status=500,
            mimetype="application/json"
        )

# ---- Static Data --------------------------------------------------------
# Serve static files (JSON, etc.) from the Files directory.
@app.route("/Data/<path:filename>", methods=["GET"])
@app.route(f'{BASE_PATH}/Data/<path:filename>', methods=["GET"])
def serve_data(filename):
    """Serve static files for debugging."""
    if ".." in filename or filename.startswith("/"):
        return Response("Forbidden", status=403)
    target = os.path.join(files_root, filename)
    if not os.path.isfile(target):
        return Response("Not found", status=404)
    return send_from_directory(files_root, filename, as_attachment=False)

@app.route("/LicenseKey", methods=["GET"])
@app.route(f'{BASE_PATH}/LicenseKey', methods=["GET"])
def license_key():
    # Lets the frontend register the key at runtime from the Azure app setting.
    return Response(LICENSE_KEY, mimetype="text/plain")

# ---------------------------------------------------------------------------
# SPA Root Routes (serve index.html for both root and sub-path)
# ============================================================================
# Flask's send_static_file('index.html') returns the frontend's index.html,
# which the browser then loads with script tags like:
#   <script src="/vue-spreadsheet-docx-mail-merge/assets/main.js"></script>
#   (when VITE_APP_BASE_PATH was set during the frontend build)
#
# When accessed at the sub-path, Flask's SPA routing must also catch requests
# like /vue-spreadsheet-docx-mail-merge/ and return index.html. This allows
# the Vue Router (or simple SPA history) to handle all routes at the correct
# base path.
# ============================================================================
@app.route("/")
def home():
    return app.send_static_file("index.html")

# If BASE_PATH is set (e.g., /vue-spreadsheet-docx-mail-merge),
# also serve index.html at that path and its trailing-slash variant
if BASE_PATH:
    @app.route(f"{BASE_PATH}/", methods=["GET"])
    def home_subpath_trailing():
        return app.send_static_file("index.html")
    
    @app.route(f"{BASE_PATH}", methods=["GET"])
    def home_subpath_notrailing():
        # Redirect /vue-spreadsheet-docx-mail-merge → /vue-spreadsheet-docx-mail-merge/
        # This ensures consistency with how the frontend's Vite build references assets
        from flask import redirect
        return redirect(f"{BASE_PATH}/", code=307)
    
    # ========================================================================
    # Serve static assets from the base path
    # ========================================================================
    # When VITE_APP_BASE_PATH is set, Vite builds assets to be served from:
    #   /vue-spreadsheet-docx-mail-merge/assets/main.js
    # 
    # This route catches ALL requests to /vue-spreadsheet-docx-mail-merge/<path>
    # and serves the corresponding static file from frontend/dist/<path>
    # ========================================================================
    @app.route(f"{BASE_PATH}/<path:filepath>", methods=["GET"])
    def serve_static_subpath(filepath):
        """
        Serve static files (CSS, JS, images, etc.) from the sub-path.
        
        Examples:
          /vue-spreadsheet-docx-mail-merge/assets/main.js → frontend/dist/assets/main.js
          /vue-spreadsheet-docx-mail-merge/assets/main.css → frontend/dist/assets/main.css
          /vue-spreadsheet-docx-mail-merge/favicon.ico → frontend/dist/favicon.ico
        """
        # Attempt to serve the file from the static directory
        try:
            return app.send_static_file(filepath)
        except:
            # If file doesn't exist, return index.html (for SPA routing)
            # This allows Vue Router to handle navigation
            return app.send_static_file("index.html")

    # ========================================================================
    # Architecture: All API endpoints are at ROOT paths only
    # ========================================================================
    # The frontend uses absolute paths (starting with /) for all API calls:
    # - fetch('/Open')
    # - fetch('/api/CollaborativeEditing/ImportFile')
    # - fetch('/LicenseKey')
    # 
    # The SPA base path is handled by:
    # - Vite build time: VITE_APP_BASE_PATH
    # - Docker build: --build-arg VITE_APP_BASE_PATH
    # - Load balancer: URL rewriting
    #
    # This ensures:
    # ✅ Works locally at root (/)
    # ✅ Works locally at sub-path
    # ✅ Works on Azure at root and sub-path
    # ========================================================================
    print(f"[app] Using clean architecture: All API endpoints at root paths", flush=True)
    print(f"[app] SPA served at: {BASE_PATH} (via Vite base path)", flush=True)

if __name__ == "__main__":
    # threaded=True so large uploads don't block the dev server
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=True) # http://localhost:5000/
    # app.run(host='', port=5001, debug=True) # http://localhost:5001/
