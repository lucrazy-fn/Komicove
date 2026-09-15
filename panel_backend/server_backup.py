"""Backup e restauração local do banco SQLite e dos arquivos publicados do PANEL."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def _db_path() -> Path:
    url = os.environ.get("PANEL_DATABASE_URL", "sqlite:///./panel.db")
    if not url.startswith("sqlite:///") or url.endswith(":memory:"):
        raise SystemExit("A rotina local suporta apenas PANEL_DATABASE_URL SQLite.")
    return Path(url.removeprefix("sqlite:///"))


def _storage_path() -> Path:
    return Path(os.environ.get("PANEL_STORAGE_DIR", "./panel_storage"))


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create(destination: Path) -> Path:
    db = _db_path().resolve(); storage = _storage_path().resolve()
    if not db.is_file(): raise SystemExit(f"Banco não encontrado: {db}")
    destination = destination.resolve(); destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="panel-backup-") as tmp:
        snapshot = Path(tmp) / "panel.db"
        source = sqlite3.connect(str(db)); target = sqlite3.connect(str(snapshot))
        try: source.backup(target)
        finally: target.close(); source.close()
        files=[]
        if storage.is_dir():
            for item in storage.rglob("*"):
                if item.is_file(): files.append((item, item.relative_to(storage).as_posix()))
        manifest={"format":"panel-server-backup","version":1,
                  "created_at":datetime.now(timezone.utc).isoformat(),
                  "database_sha256":_sha(snapshot),"files":[]}
        with zipfile.ZipFile(destination,"w",zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot,"database/panel.db")
            for item, relative in files:
                archive.write(item,"storage/"+relative)
                manifest["files"].append({"path":relative,"sha256":_sha(item),"size":item.stat().st_size})
            archive.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
    return destination


def restore(archive_path: Path, *, database: Path|None=None, storage: Path|None=None) -> None:
    database=(database or _db_path()).resolve(); storage=(storage or _storage_path()).resolve()
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    with zipfile.ZipFile(archive_path) as archive:
        try: manifest=json.loads(archive.read("manifest.json"))
        except (KeyError,json.JSONDecodeError) as exc: raise SystemExit("Backup inválido: manifesto ausente.") from exc
        if manifest.get("format")!="panel-server-backup" or manifest.get("version")!=1:
            raise SystemExit("Formato de backup não reconhecido.")
        names=set(archive.namelist())
        if "database/panel.db" not in names: raise SystemExit("Backup sem banco.")
        if database.is_file(): shutil.copy2(database, database.with_name(database.name+f".before-restore-{stamp}"))
        if storage.is_dir(): shutil.copytree(storage, storage.with_name(storage.name+f".before-restore-{stamp}"))
        with tempfile.TemporaryDirectory(prefix="panel-restore-") as tmp:
            root=Path(tmp); archive.extract("database/panel.db",root)
            extracted=root/"database/panel.db"; database.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(extracted,database)
            storage.mkdir(parents=True,exist_ok=True)
            for name in names:
                if not name.startswith("storage/") or name.endswith("/"): continue
                rel=Path(name.removeprefix("storage/")); target=(storage/rel).resolve()
                if storage not in target.parents: raise SystemExit("Backup contém caminho inválido.")
                target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(archive.read(name))
    print(f"Restauração concluída. Cópias anteriores terminam em .before-restore-{stamp}.")


def main():
    parser=argparse.ArgumentParser(description="Backup/restauração local do servidor PANEL")
    sub=parser.add_subparsers(dest="command",required=True)
    make=sub.add_parser("create"); make.add_argument("destination",type=Path)
    put=sub.add_parser("restore"); put.add_argument("archive",type=Path); put.add_argument("--database",type=Path); put.add_argument("--storage",type=Path)
    args=parser.parse_args()
    if args.command=="create": print(f"Backup criado: {create(args.destination)}")
    else: restore(args.archive,database=args.database,storage=args.storage)


if __name__=="__main__": main()
