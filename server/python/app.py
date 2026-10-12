import atexit
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

project_root = Path(__file__).resolve().parent
host_directory = project_root / "collaboration-host"
host_executable = host_directory / "CollaborationHost.exe"
health_url = "http://127.0.0.1:5001/health"

collaboration_process = None


def stop_collaboration_host() -> None:
    global collaboration_process

    if collaboration_process is None:
        return

    if collaboration_process.poll() is not None:
        collaboration_process = None
        return

    try:
        if sys.platform == "win32":
            os.kill(
                collaboration_process.pid,
                signal.CTRL_BREAK_EVENT
            )
        else:
            collaboration_process.terminate()

        collaboration_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        collaboration_process.kill()
        collaboration_process.wait()
    finally:
        collaboration_process = None


def wait_for_collaboration_host() -> bool:
    for _ in range(30):
        if collaboration_process.poll() is not None:
            return False

        try:
            with urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    return True
        except URLError:
            time.sleep(1)

    return False


def start_collaboration_host() -> None:
    global collaboration_process

    if not host_executable.exists():
        raise FileNotFoundError(
            f"CollaborationHost.exe was not found at "
            f"{host_executable}"
        )

    collaboration_process = subprocess.Popen(
        [str(host_executable)],
        cwd=str(host_directory),
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP
            if sys.platform == "win32"
            else 0
        )
    )

    if not wait_for_collaboration_host():
        stop_collaboration_host()

        raise RuntimeError(
            "The collaboration service failed to start."
        )


def main() -> None:
    print("=" * 52)
    print("Starting Spreadsheet Version History backend")
    print("=" * 52)

    start_collaboration_host()

    print("Backend: http://127.0.0.1:5001")
    print("SignalR: http://127.0.0.1:5001/collaborationhub")
    print("Press Ctrl+C to stop.")
    print("=" * 52)

    try:
        collaboration_process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        stop_collaboration_host()


atexit.register(stop_collaboration_host)

if __name__ == "__main__":
    main()