
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from typing import Optional

from komicove_app.storage import APPDATA_DIR as _APPDATA
os.makedirs(_APPDATA, exist_ok=True)
SESSION_FILE = os.path.join(_APPDATA, "auth_session.json")


@dataclass
class LocalSession:
    token: str
    user_id: str
    username: str
    display_name: str
    is_moderator: bool = False
    role: str = "user"


def load_session() -> Optional[LocalSession]:
    if not os.path.isfile(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return LocalSession(**data)
    except Exception:


        return None


def save_session(session: LocalSession) -> None:
    fd, temp_path = tempfile.mkstemp(prefix="session-", suffix=".tmp", dir=_APPDATA)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(asdict(session), f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, SESSION_FILE)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def clear_session() -> None:
    if os.path.isfile(SESSION_FILE):
        os.remove(SESSION_FILE)
