"""Library backup and restore (one zip: database, book copies and covers)."""
import json
import shutil
import sqlite3
import tempfile
import time
import zipfile

from datetime import datetime
from pathlib import Path


APP_TAG = "epub-reader-backup"
_ALLOWED_DIRS = ("books/", "covers/")


class BackupError(Exception):
    pass


def create_backup(library, dest: Path, progress=None) -> dict:
    """Write a consistent snapshot of the whole library to `dest` (a .zip file).
    `progress(done, total)` is called after each file."""
    dest = Path(dest)
    files = [(d, p) for d in (library.books_dir, library.covers_dir)
             for p in sorted(d.rglob("*")) if p.is_file()]
    total = len(files) + 1
    tmp = Path(tempfile.mkdtemp()) / "library.db"
    try:
        snapshot = sqlite3.connect(tmp)
        try:
            library.db.backup(snapshot)  # consistent copy even while the app is open
        finally:
            snapshot.close()
        info = dict(app=APP_TAG, created=datetime.now().isoformat(timespec="seconds"),
                    books=library.count())
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("backup.json", json.dumps(info))
            z.write(tmp, "library.db")
            if progress:
                progress(1, total)
            for i, (folder, f) in enumerate(files, 2):
                z.write(f, f"{folder.name}/{f.relative_to(folder).as_posix()}")
                if progress:
                    progress(i, total)
        return info
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)


def inspect_backup(path: Path) -> dict:
    """Validate a backup file and return its info; raises BackupError if unusable."""
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if "library.db" not in names:
                raise BackupError("This zip is not a Book Reader backup (no library.db).")
            info = json.loads(z.read("backup.json")) if "backup.json" in names else {}
            info.setdefault("books", sum(1 for n in names if n.startswith("books/")))
            info["files"] = len(names)
            return info
    except zipfile.BadZipFile as exc:
        raise BackupError("That file is not a valid zip archive.") from exc


def restore_backup(library, path: Path, progress=None) -> Path:
    """Replace the library with the backup. The current library is first saved to
    <data>/safety-backups/, whose path is returned. Raises BackupError on bad input."""
    path = Path(path)
    inspect_backup(path)
    safety = library.root / "safety-backups" / f"before-restore-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    create_backup(library, safety)
    library.close()
    try:
        for name in ("books", "covers"):
            shutil.rmtree(library.root / name, ignore_errors=True)
        (library.root / "library.db").unlink(missing_ok=True)
        with zipfile.ZipFile(path) as z:
            members = [m for m in z.namelist() if _safe_member(m)]
            for i, m in enumerate(members, 1):
                target = library.root / m
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(m) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
                if progress:
                    progress(i, len(members))
    finally:
        library.reopen()
    return safety


def _safe_member(name: str) -> bool:
    parts = Path(name).parts
    if ".." in parts or name.startswith("/") or name.endswith("/"):
        return False
    return name == "library.db" or name.startswith(_ALLOWED_DIRS)
