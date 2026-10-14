from flask import Flask, request, Response, send_file, send_from_directory
import json
from flask_cors import CORS
from flask_sock import Sock

import redis
import os
import sys
import traceback
import uuid
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
os.environ.setdefault("PYTHONNET_RUNTIME", "coreclr")
if not os.environ.get("DOTNET_ROOT"):
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
        os.environ["DOTNET_ROOT"] = _candidate
os.environ.setdefault("DOTNET_ROLL_FORWARD", "LatestMajor")

# Pre-configure LD_LIBRARY_PATH on Linux for native library discovery (especially SkiaSharp)
# This MUST run before CLR initialization to ensure native libraries are found when the runtime
# loads managed assemblies that depend on native .so files (libSkiaSharp.so, libgdiplus, etc.)
if sys.platform.startswith("linux"):
    # System graphics libraries that SkiaSharp and other rendering libraries depend on
    base_ld_paths = "/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu"
    existing_ld = os.environ.get("LD_LIBRARY_PATH", "").strip()
    if existing_ld:
        new_ld = base_ld_paths + ":" + existing_ld
    else:
        new_ld = base_ld_paths
    os.environ["LD_LIBRARY_PATH"] = new_ld
    print(f"[app] Pre-configured LD_LIBRARY_PATH for Linux: {new_ld[:120]}...", flush=True)

# Import clr AFTER the env-var setup above.
import clr  # noqa: E402  (must come after PYTHONNET_RUNTIME setup)

app = Flask(
__name__,
static_folder='frontend/dist',
static_url_path=''
)

sock = Sock(app)

# ============================================================================
# Redis Configuration
# ============================================================================

def load_application_settings():
    settings_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "appsettings.json"
    )

    if not os.path.isfile(settings_path):
        raise FileNotFoundError(
            f"Configuration file was not found: {settings_path}"
        )

    with open(settings_path, "r", encoding="utf-8") as settings_file:
        return json.load(settings_file)


def create_redis_client():
    application_settings = load_application_settings()
    redis_settings = application_settings.get("Redis", {})

    redis_host = str(
        redis_settings.get("Host", "")
    ).strip()
    redis_port = int(
        redis_settings.get("Port", 6379)
    )
    redis_password = str(
        redis_settings.get("Password", "")
    ).strip()
    redis_ssl = bool(
        redis_settings.get("Ssl", False)
    )

    if not redis_host or redis_host == "YOUR_REDIS_HOST":
        raise RuntimeError(
            "Configure Redis.Host in appsettings.json."
        )

    if redis_password == "YOUR_REDIS_ACCESS_KEY":
        raise RuntimeError(
            "Configure Redis.Password in appsettings.json."
        )

    client = redis.Redis(
        host=redis_host,
        port=redis_port,
        password=redis_password or None,
        ssl=redis_ssl,
        decode_responses=True,
        socket_connect_timeout=10,
        socket_timeout=10,
        health_check_interval=30
    )

    client.ping()

    print(
        f"[Redis] Connected to {redis_host}:{redis_port}",
        flush=True
    )

    return client


redis_client = create_redis_client()

# ---- Minimal CORS + large-file support ----
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024 # 500 MB
app.config['MAX_FORM_MEMORY_SIZE'] = 500 * 1024 * 1024 # 500 MB

# ============================================================================
# Sub-path support for GCP Load Balancer path mapping
# ============================================================================
# When deployed behind a load balancer with path mapping, the application
# can be accessed at both the root path (/) and the sub-path. This is
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

# ============================================================================
# Collaboration Redis Constants
# ============================================================================

VERSION_INFO_SUFFIX = "_versioninfo"
REVISION_INFO_SUFFIX = "_revisioninfo"
ACTIONS_TO_REMOVE_SUFFIX = "_actionstoremove"

SAVE_THRESHOLD = 5

CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=False,
    expose_headers=["Content-Disposition", "Content-Length", "Content-Type"],
)

try:
    redis_client.ping()

    print("[REDIS] Connected successfully")

except Exception as ex:

    print(f"[REDIS] Connection failed: {ex}")

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
#   2. netstandard2.0/publish/    (fallback — compatible but older)
#   3. Current directory           (last resort — some Docker layouts flatten here)
_publish_candidate_a = os.path.join(
    current_working_directory,
    "NETStandardWrapperLibrary/WebServiceLibrary/bin/Release/net10.0/publish/"
)
_publish_candidate_b = os.path.join(
    current_working_directory,
    "NETStandardWrapperLibrary/WebServiceLibrary/bin/Release/net10.0/linux-x64/publish/"
)
_publish_candidate_c = os.path.join(
    current_working_directory,
    "NETStandardWrapperLibrary/WebServiceLibrary/runtimes/"
)

# Use the first candidate that exists
publish_base = None
for candidate in [_publish_candidate_a, _publish_candidate_b]:
    if os.path.isdir(candidate):
        publish_base = candidate
        break

if not publish_base:
    # Fallback to candidate_c if primary locations don't exist
    if os.path.isdir(_publish_candidate_c):
        publish_base = _publish_candidate_c
    else:
        # Last resort: use candidate_a even if it doesn't exist yet
        publish_base = _publish_candidate_a

print(f"[app] Using publish base: {publish_base}", flush=True)

files_root = os.path.join(current_working_directory, "Files")
data_root = os.path.join(files_root, "Data")
OUTPUT_DIRECTORY = os.path.join(files_root, "Output")

# Immutable sample workbook (never overwritten)
SAMPLE_WORKBOOK = os.path.join(data_root, "Sample.xlsx")

# Make sure the runtime folders exist (idempotent).
os.makedirs(data_root, exist_ok=True)
os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

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
if sys.platform.startswith("win"):
    # Windows: Check win-x64/native and root
    native_search_dirs = [
        os.path.join(runtimes_base, "win-x64", "native"),
        publish_base,
    ]
elif sys.platform.startswith("linux"):
    # Linux: Check linux-x64/native and root
    native_search_dirs = [
        os.path.join(runtimes_base, "linux-x64", "native"),
        publish_base,
    ]

# Add all found native directories to PATH (Windows) or LD_LIBRARY_PATH (Linux)
# IMPORTANT: Build the full LD_LIBRARY_PATH BEFORE the loop to avoid overwriting
if sys.platform.startswith("linux"):
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

elif sys.platform.startswith("win"):
    # Windows: Add native directories to PATH
    for native_dir in native_search_dirs:
        if os.path.isdir(native_dir):
            os.environ["PATH"] = native_dir + os.pathsep + os.environ.get("PATH", "")
            print(f"[app] Added Windows native path: {native_dir}", flush=True)

sys.path.insert(0, publish_base)
print(f"[app] Added publish base to sys.path: {publish_base}", flush=True)

_ASSEMBLY_NAMES = [
    "Syncfusion.EJ2.Spreadsheet",
    "Syncfusion.XlsIO.Portable",
    "HarfBuzzSharp",
    "Newtonsoft.Json",
    "SkiaSharp",
    "SkiaSharp.HarfBuzz",
    "Syncfusion.Licensing",
    "Syncfusion.Compression.Portable",
    "Syncfusion.OfficeChart.Portable",
    "Syncfusion.SkiaSharpHelper.Portable",
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
        # Critical assemblies for PDF export — fail fast
        if _name in ("SkiaSharp", "Syncfusion.DocIORenderer.Portable", "Syncfusion.Pdf.Portable"):
            print(f"[app] FATAL: {_name} is required for PDF export!", flush=True)
            raise

# ============================================================================
# Python-side imports from the C# wrapper namespace.
# ============================================================================
from WebServiceLibrary import SpreadsheetEditor, SpreadsheetCollaborationWrapper
from Syncfusion.EJ2.Spreadsheet import SaveSettings, SaveType
from Syncfusion.Licensing import SyncfusionLicenseProvider
from System import Enum
from System.IO import SeekOrigin

# ---------------------------------------------------------------------------
# Register the Syncfusion license
LICENSE_KEY = os.environ.get("SYNCFUSION_LICENSE_KEY", "")
SyncfusionLicenseProvider.RegisterLicense(LICENSE_KEY)

spreadEditor = SpreadsheetEditor()
collabWrapper = SpreadsheetCollaborationWrapper()

try:
    if not hasattr(spreadEditor, 'Open'):
        raise AttributeError("SpreadsheetEditor missing Open method")
    if not hasattr(collabWrapper, 'ImportFile'):
        raise AttributeError("SpreadsheetCollaborationWrapper missing ImportFile method")
    if not hasattr(collabWrapper, 'ApplyCollaborativeActions'):
        raise AttributeError("SpreadsheetCollaborationWrapper missing ApplyCollaborativeActions method")
    print("[app] [OK] Spreadsheet wrappers initialized successfully", flush=True)
except Exception as e:
    print(f"[app] [ERR] Wrapper initialization failed: {e}", flush=True)
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

                # Cleanup empty room and perform final save

                if len(rooms[room_name]) == 0:
                    del rooms[room_name]

                    # Final save: include all remaining unsaved actions
                    try:
                        file_name = "Sample.xlsx"  # Default file name for final save
                        
                        # Retrieve all remaining unsaved actions (both active and threshold-selected)
                        all_unsaved_actions = get_all_unsaved_actions(room_name)
                        
                        if all_unsaved_actions:
                            # Temporarily store all unsaved actions for process_save_actions
                            redis_client.delete(get_actions_to_remove_key(room_name))
                            for action in all_unsaved_actions:
                                redis_client.rpush(
                                    get_actions_to_remove_key(room_name),
                                    json.dumps(action)
                                )
                            
                            process_save_actions(
                                room_name,
                                file_name,
                                partial_save=False
                            )
                        else:
                            # No unsaved actions, just clear records
                            clear_records(room_name, partial_save=False)
                        
                    except Exception as ex:
                        print(f"[WORKBOOK SAVE] Failed for room {room_name}: {ex}")

            sessions.pop(
                connection_id,
                None
            )

        print(
            f"[WS] Disconnected: {connection_id}"
        )


def sanitize_file_name(file_name):
    """Prevent path traversal; return basename only."""
    return os.path.basename(file_name) if file_name else "Sample.xlsx"

def sanitize_room_name(room_name):
    """Prevent path traversal; return safe room name."""
    if not room_name:
        return "default"
    # Allow alphanumeric, dash, underscore only
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', room_name)
    return sanitized if sanitized else "default"

def get_output_workbook_path(file_name):
    """Get path to output workbook (shared across all rooms)."""
    safe_file_name = sanitize_file_name(file_name)
    
    if not safe_file_name.lower().endswith(".xlsx"):
        safe_file_name += ".xlsx"
    
    return os.path.join(
        OUTPUT_DIRECTORY,
        safe_file_name
    )

def get_source_workbook_path(file_name):
    """Get source workbook: output if exists, else immutable Sample.xlsx."""
    output_workbook_path = get_output_workbook_path(file_name)
    
    if os.path.isfile(output_workbook_path):
        return output_workbook_path
    
    return SAMPLE_WORKBOOK

def get_version_key(room_name):

    return f"{room_name}{VERSION_INFO_SUFFIX}"


def get_revision_key(room_name):

    return f"{room_name}{REVISION_INFO_SUFFIX}"


def get_action_remove_key(room_name):

    return f"{room_name}{ACTIONS_TO_REMOVE_SUFFIX}"


def get_room_version(room_name):

    value = redis_client.get(
        get_version_key(room_name)
    )

    return int(value or 0)


def increment_room_version(room_name):

    return redis_client.incr(
        get_version_key(room_name)
    )


def save_action_to_redis(
    room_name,
    action
):

    redis_client.rpush(
        room_name,
        json.dumps(action)
    )

def get_action_count(
    room_name
):

    return redis_client.llen(
        room_name
    )

def get_pending_actions(
    room_name,
    start_index=0,
    end_index=-1
):

    actions = redis_client.lrange(
        room_name,
        start_index,
        end_index
    )

    return [
        json.loads(item)
        for item in actions
    ]

def get_pending_operations(
    room_name,
    start_index=0,
    end_index=-1
):

    processing_actions = redis_client.lrange(
        get_actions_to_remove_key(
            room_name
        ),
        start_index,
        end_index
    )

    active_actions = redis_client.lrange(
        room_name,
        start_index,
        end_index
    )

    result = []

    result.extend(
        [
            json.loads(item)
            for item in processing_actions
        ]
    )

    result.extend(
        [
            json.loads(item)
            for item in active_actions
        ]
    )

    return result

def get_effective_pending_operations(
    room_name,
    client_version
):

    revision = get_room_revision(
        room_name
    )

    effective_version = (
        revision * SAVE_THRESHOLD
    )

    adjusted_version = (
        client_version -
        effective_version
    )

    if adjusted_version < 0:
        return []

    actions = redis_client.lrange(
        room_name,
        adjusted_version,
        -1
    )

    return [
        json.loads(action)
        for action in actions
    ]

def get_actions_from_server(
    room_name,
    last_synced_version
):

    actions = get_effective_pending_operations(
        room_name,
        last_synced_version
    )

    actions = [
        action
        for action in actions
        if action.get(
            "version",
            0
        ) > last_synced_version
    ]

    actions.sort(
        key=lambda x: x.get(
            "version",
            0
        )
    )

    return actions


def get_room_revision(
    room_name
):

    value = redis_client.get(
        get_revision_key(room_name)
    )

    return int(value or 0)

def increment_room_revision(
    room_name
):

    return redis_client.incr(
        get_revision_key(room_name)
    )

def get_effective_version(
    room_name
):

    revision = get_room_revision(
        room_name
    )

    return revision * SAVE_THRESHOLD

def get_actions_to_remove_key(
    room_name
):

    return (
        f"{room_name}"
        f"{ACTIONS_TO_REMOVE_SUFFIX}"
    )

def process_action_threshold(
    room_name
):

    length = redis_client.llen(
        room_name
    )

    cache_limit = (
        SAVE_THRESHOLD * 2
    )

    if length == 0:
        return []

    if length % cache_limit != 0:
        return []

    old_actions = redis_client.lrange(
        room_name,
        0,
        SAVE_THRESHOLD - 1
    )

    if old_actions:

        for action in old_actions:

            redis_client.rpush(
                get_actions_to_remove_key(
                    room_name
                ),
                action
            )

    redis_client.ltrim(
        room_name,
        SAVE_THRESHOLD,
        -1
    )

    revision = increment_room_revision(
        room_name
    )

    print(
        f"[REDIS] Revision "
        f"incremented to {revision}"
    )

    print(
        f"[REDIS] Moved "
        f"{len(old_actions)} actions "
        f"to actionstoremove"
    )

    return old_actions

def get_actions_to_save(
    room_name
):

    actions = redis_client.lrange(
        get_actions_to_remove_key(
            room_name
        ),
        0,
        -1
    )

    return [
        json.loads(action)
        for action in actions
    ]

def get_actions_to_save_count(
    room_name
):

    return redis_client.llen(
        get_actions_to_remove_key(
            room_name
        )
    )

def get_room_actions_for_workbook(
    room_name
):

    actions = []

    actions.extend(
        get_pending_operations(
            room_name
        )
    )

    return actions

def get_all_unsaved_actions(room_name):
    """
    Retrieve every remaining unsaved action for the room.
    
    Combines:
    - Active pending actions (main room action list)
    - Threshold-selected actions (actions moved to actionstoremove queue)
    
    Deduplicates by server version and sorts by version ascending.
    
    Returns:
    - List of all unsaved actions, deduplicated and sorted by version
    """
    try:
        # Retrieve active pending actions from main room list
        active_actions_raw = redis_client.lrange(room_name, 0, -1)
        active_actions = [
            json.loads(item) for item in (active_actions_raw or [])
        ]
    except Exception as e:
        print(f"[SAVE] Error retrieving active actions for {room_name}: {e}")
        active_actions = []
    
    try:
        # Retrieve threshold-selected actions from actionstoremove queue
        threshold_actions_raw = redis_client.lrange(
            get_actions_to_remove_key(room_name), 0, -1
        )
        threshold_actions = [
            json.loads(item) for item in (threshold_actions_raw or [])
        ]
    except Exception as e:
        print(f"[SAVE] Error retrieving threshold actions for {room_name}: {e}")
        threshold_actions = []
    
    # Combine both action collections
    all_actions = active_actions + threshold_actions
    
    if not all_actions:
        return []
    
    # Deduplicate by server version (unique key for each action)
    seen_versions = set()
    unique_actions = []
    
    for action in all_actions:
        version = action.get("version")
        if version is not None and version not in seen_versions:
            seen_versions.add(version)
            unique_actions.append(action)
    
    # Sort by server version ascending
    unique_actions.sort(key=lambda a: a.get("version", 0))
    
    return unique_actions

def clear_records(
    room_name,
    partial_save=False
):

    if not partial_save:

        redis_client.delete(room_name)

        redis_client.delete(
            get_version_key(room_name)
        )

        redis_client.delete(
            get_revision_key(room_name)
        )

    redis_client.delete(
        get_actions_to_remove_key(
            room_name
        )
    )

def process_save_actions(
    room_name,
    file_name,
    partial_save=True
):
    """Save actions to shared output workbook."""
    actions = get_actions_to_save(room_name)

    if not actions:
        print(f"[WORKBOOK SAVE] No unsaved actions for room: {room_name}")
        return True

    # Get source workbook (output if exists, else immutable Sample.xlsx)
    source_path = get_source_workbook_path(file_name)
    if not os.path.isfile(source_path):
        print(f"[WORKBOOK SAVE] Failed for room {room_name}: Source workbook not found at {source_path}")
        return False

    temp_path = None
    try:
        with open(source_path, "rb") as f:
            workbook_bytes = f.read()

        actions_json = json.dumps(actions)

        # Apply actions via wrapper
        updated_bytes = collabWrapper.ApplyCollaborativeActions(
            workbook_bytes,
            actions_json
        )

        # Save to temporary file first
        target_path = get_output_workbook_path(file_name)
        temp_path = target_path + ".tmp.xlsx"

        print(f"[WORKBOOK SAVE] Room={room_name}, File={target_path}, Actions={len(actions)}")

        with open(target_path, "wb") as f:
            f.write(updated_bytes)

        # Atomically replace (do not pre-delete target)
        # os.replace(target_path, target_path)

        # Clear only the saved actions
        clear_records(room_name, partial_save)

        print(f"[WORKBOOK SAVE] Saved: {target_path}")
        return True

    except Exception as ex:
        print(f"[WORKBOOK SAVE] Failed for room {room_name}: {ex}")
        # Clean up temp file if it exists
        if temp_path:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass
        return False

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

        file_name = sanitize_file_name(request_data.get("fileName", "Sample.xlsx"))
        room_name = sanitize_room_name(request_data.get("roomName", "default"))

        print(f"[COLLAB] ImportFile File={file_name}, Room={room_name}")

        # Get source workbook (output if exists, else immutable Sample.xlsx)
        source_path = get_source_workbook_path(file_name)
        if not os.path.isfile(source_path):
            error_payload = json.dumps(
                {"error": f"Workbook not found: {source_path}"}
            )
            return Response(error_payload, status=404, mimetype='application/json')

        with open(source_path, "rb") as f:
            workbook_bytes = f.read()

        # Get pending actions for this room
        actions = get_room_actions_for_workbook(room_name)
        actions_json = json.dumps(actions)
        current_version = get_room_version(room_name)

        # Apply actions and get Spreadsheet JSON
        result_json = spreadEditor.OpenWithActions(
            workbook_bytes,
            actions_json
        )

        return Response(
            result_json,
            mimetype="application/json"
        )

    except Exception as ex:
        print(f"[COLLAB] ImportFile Error: {str(ex)}")
        return Response(
            json.dumps({"error": str(ex)}),
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

        version = increment_room_version(room_name)
        data["version"] = version

        print(
            f"[REDIS] Room={room_name} "
            f"Version={version}"
        )
        save_action_to_redis(
            room_name,
            data
        )
        moved_actions = (
            process_action_threshold(
                room_name
            )
        )

        if moved_actions:

            print(
                f"[REDIS] "
                f"Save queue size="
                f"{len(moved_actions)}"
            )
            save_count = (
                get_actions_to_save_count(
                    room_name
                )
            )
            file_name = sanitize_file_name(data.get("fileName", "Sample.xlsx"))
            process_save_actions(
                room_name,
                file_name,
                True
            )
            print(
                redis_client.llen(
                    get_actions_to_remove_key(
                        room_name
                    )
                )
            )

            print(
                f"[REDIS] ActionsToSave="
                f"{save_count}"
            )
        
        print(
            redis_client.llen(
                get_actions_to_remove_key(
                    room_name
                )
            )
        )

        count = get_action_count(
            room_name
        )

        print(
            f"[REDIS] Room={room_name} "
            f"Actions={count}"
        )
        pending_actions = (
            get_pending_operations(
                room_name
            )
        )

        print(
            f"[REDIS] PendingOperations="
            f"{len(pending_actions)}"
        )

        effective_version = (
            get_effective_version(
                room_name
            )
        )
        effective_actions = (
            get_effective_pending_operations(
                room_name,
                data.get(
                    "clientVersion",
                    0
                )
            )
        )

        print(
            f"[REDIS] EffectivePending="
            f"{len(effective_actions)}"
        )

        print(
            f"[REDIS] EffectiveVersion="
            f"{effective_version}"
        )

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
    "/api/CollaborativeEditing/GetActionsFromServer",
    methods=["POST"]
)
@app.route(
    f"{BASE_PATH}/api/CollaborativeEditing/GetActionsFromServer",
    methods=["POST"]
)
def get_actions_from_server_endpoint():

    try:

        data = request.get_json()

        if not data:

            return Response(
                json.dumps([]),
                mimetype="application/json"
            )

        room_name = data.get(
            "roomName"
        )

        if not room_name:

            return Response(
                json.dumps([]),
                mimetype="application/json"
            )

        last_synced_version = int(
            data.get(
                "version",
                0
            )
        )

        actions = (
            get_actions_from_server(
                room_name,
                last_synced_version
            )
        )

        print(
            f"[COLLAB] "
            f"GetActionsFromServer "
            f"Room={room_name} "
            f"Version={last_synced_version} "
            f"Returned={len(actions)}"
        )

        return Response(
            json.dumps(actions),
            mimetype="application/json"
        )

    except Exception as ex:

        print(
            f"[COLLAB] "
            f"GetActionsFromServer Error: "
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






# ---- Static Data (catalog + common-fields) --------------------------------
# Mirrors wwwroot/Data in the C# project so the client can fetch them
# directly as plain JSON. Useful as a debugging escape hatch.
@app.route("/Data/<path:filename>", methods=["GET"])
@app.route(f'{BASE_PATH}/Data/<path:filename>', methods=["GET"])
def serve_data(filename):
    """Serve catalog / common-fields JSON for debugging."""
    if ".." in filename or filename.startswith("/"):
        return Response("Forbidden", status=403)
    target = os.path.join(data_root, filename)
    if not os.path.isfile(target):
        return Response("Not found", status=404)
    return send_from_directory(data_root, filename, as_attachment=False)

@app.route("/LicenseKey", methods=["GET"])
@app.route(f'{BASE_PATH}/LicenseKey', methods=["GET"])
def license_key():
    # Lets the frontend register the key at runtime from the Azure app setting.
    return Response(LICENSE_KEY, mimetype="text/plain")

@app.route("/health", methods=["GET"])
@app.route(f'{BASE_PATH}/health', methods=["GET"])
def health_check():
    """Health check endpoint for deployment verification."""
    try:
        redis_client.ping()
        return Response(
            json.dumps({"status": "healthy", "redis": "connected"}),
            status=200,
            mimetype="application/json"
        )
    except Exception as ex:
        return Response(
            json.dumps({"status": "unhealthy", "error": str(ex)}),
            status=503,
            mimetype="application/json"
        )

# ---------------------------------------------------------------------------
# SPA Root Routes (serve index.html for both root and sub-path)
# ============================================================================
@app.route("/")
def home():
    return app.send_static_file("index.html")

# If BASE_PATH is set, also serve index.html at that path
if BASE_PATH:
    @app.route(f"{BASE_PATH}/", methods=["GET"])
    def home_subpath_trailing():
        return app.send_static_file("index.html")
    
    @app.route(f"{BASE_PATH}", methods=["GET"])
    def home_subpath_notrailing():
        from flask import redirect
        return redirect(f"{BASE_PATH}/", code=307)
    
    @app.route(f"{BASE_PATH}/<path:filepath>", methods=["GET"])
    def serve_static_subpath(filepath):
        """Serve static files from the sub-path."""
        try:
            return app.send_static_file(filepath)
        except:
            return app.send_static_file("index.html")

if __name__ == "__main__":
    # threaded=True so large uploads don't block the dev server
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=True) # http://localhost:5000/
    # app.run(host='', port=5001, debug=True) # http://localhost:5001/
