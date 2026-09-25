import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

def _ensure_local_api():
    pass
    if getattr(sys, "frozen", False):return None
    from komicove_client import api_client
    host=urlparse(api_client.BASE_URL).hostname
    if host not in {"127.0.0.1","localhost"}:return None
    try:
        import requests
        if requests.get(f"{api_client.BASE_URL}/health",timeout=.45).ok:return None
    except Exception:pass
    flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
    project_root=Path(__file__).resolve().parent.parent
    venv_python=project_root / ".venv" / "Scripts" / "python.exe"
    server_python=str(venv_python) if venv_python.is_file() else sys.executable
    process=subprocess.Popen([server_python,"-m","uvicorn","komicove_backend.api.app:app",
        "--host","127.0.0.1","--port",str(urlparse(api_client.BASE_URL).port or 8000)],
        cwd=str(project_root),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    for _ in range(20):
        if process.poll() is not None:return None
        try:
            if requests.get(f"{api_client.BASE_URL}/health",timeout=.25).ok:return process
        except Exception:time.sleep(.1)
    return process

def main() -> None:
    from komicove_app.library_views import LibraryWindow
    server=_ensure_local_api()
    try:
        app = LibraryWindow()
        app.mainloop()
    finally:
        if server and server.poll() is None:server.terminate()
