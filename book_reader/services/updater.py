"""Update checking, downloading and installing. Qt-free.

The update source (constants.UPDATE_URL) can be either
  * a small JSON "manifest" you publish with each release:
        {"version": "1.2.0", "url": "https://.../BookReader-Setup-1.2.0.exe",
         "sha256": "<64 hex characters>", "notes": "what is new (Markdown)", "page": "https://..."}
    (tools/make_manifest.py writes it for you), or
  * a GitHub "latest release" API link:
        https://api.github.com/repos/<owner>/<repo>/releases/latest
    (the installer is the release asset named like *Setup*.exe; its checksum is read from the
    asset's digest, or from a "<installer>.sha256" file attached to the same release).

Safety rules: only HTTPS addresses are used (plain http only for localhost, for testing);
redirects are re-checked; an installer is never started unless its SHA-256 matches.
"""
import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from book_reader import __version__
from book_reader.constants import DATA_DIR

TIMEOUT = 12
MAX_JSON = 1_000_000
UPDATES_DIR = DATA_DIR / "updates"

# Inno Setup switches: silent upgrade, close the running app, start the new version afterwards
# (/RELAUNCH=1 is read by installer.iss; other silent installs do not start the app).
INSTALLER_ARGS = ["/SILENT", "/SP-", "/SUPPRESSMSGBOXES", "/NORESTART",
                  "/CLOSEAPPLICATIONS", "/RELAUNCH=1"]


class UpdateError(Exception):
    """Anything that goes wrong; the message is written for the user."""


@dataclass
class UpdateInfo:
    version: str
    url: str = ""        # the installer to download
    sha256: str = ""     # its checksum (required for installing automatically)
    notes: str = ""      # what is new (Markdown / plain text)
    page: str = ""       # web page to open when the app cannot install by itself
    size: int = 0


# -- versions ------------------------------------------------------------------------- #

_VER = re.compile(r"^\s*v?(\d+(?:\.\d+){0,3})(.*)$", re.I)


def parse_version(text) -> tuple | None:
    m = _VER.match(str(text or ""))
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def is_prerelease(text) -> bool:
    """'1.3.0-beta1' or '1.3rc2' (anything after the numbers except +build metadata)."""
    m = _VER.match(str(text or ""))
    rest = m.group(2).strip() if m else ""
    return bool(rest) and not rest.startswith("+")


def is_newer(latest, current) -> bool:
    a, b = parse_version(latest), parse_version(current)
    if a is None or b is None:
        return False
    pad = lambda v: v + (0,) * (4 - len(v))
    return pad(a) > pad(b)


# -- network -------------------------------------------------------------------------- #

def _check_url(url: str) -> str:
    u = urllib.parse.urlparse(str(url or ""))
    if u.scheme == "https" and u.hostname:
        return url
    if u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1", "::1"):
        return url   # local testing only
    raise UpdateError("Refusing to use an address that is not HTTPS.")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)   # a redirect must not downgrade to plain http
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url: str):
    req = urllib.request.Request(_check_url(url), headers={
        "User-Agent": f"BookReader/{__version__}", "Accept": "application/json, */*"})
    try:
        return urllib.request.build_opener(_SafeRedirect).open(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"The update server answered with an error ({exc.code}).") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        raise UpdateError(f"Could not reach the update server ({reason}).") from exc


def _get_json(url: str):
    try:
        with _open(url) as resp:
            raw = resp.read(MAX_JSON + 1)
        if len(raw) > MAX_JSON:
            raise UpdateError("The update information is unexpectedly large.")
        return json.loads(raw.decode("utf-8"))
    except UpdateError:
        raise
    except (OSError, ValueError) as exc:
        raise UpdateError("The update server sent information the app cannot read.") from exc


def _clean_sha(text) -> str:
    m = re.search(r"\b([0-9a-fA-F]{64})\b", str(text or ""))
    return m.group(1).lower() if m else ""


# -- reading the two supported sources -------------------------------------------------- #

def _manifest_info(d: dict) -> UpdateInfo:
    url = str(d.get("url") or "")
    if url:
        _check_url(url)
    return UpdateInfo(version=str(d.get("version") or "").strip(), url=url,
                      sha256=_clean_sha(d.get("sha256")), notes=str(d.get("notes") or ""),
                      page=str(d.get("page") or ""), size=int(d.get("size") or 0))


def _github_info(d: dict):
    if d.get("draft") or d.get("prerelease"):
        return None
    assets = [a for a in (d.get("assets") or []) if isinstance(a, dict)]
    pick = (next((a for a in assets if re.search(r"setup.*\.exe$", a.get("name", ""), re.I)), None)
            or next((a for a in assets if a.get("name", "").lower().endswith(".exe")), None))
    sha, url = "", ""
    if pick:
        url = str(pick.get("browser_download_url") or "")
        digest = str(pick.get("digest") or "")
        if digest.lower().startswith("sha256:"):
            sha = _clean_sha(digest)
        if not sha:   # a "<installer>.sha256" file attached to the release
            side = next((a for a in assets if a.get("name") == pick.get("name", "") + ".sha256"), None)
            if side and side.get("browser_download_url"):
                try:
                    with _open(side["browser_download_url"]) as resp:
                        sha = _clean_sha(resp.read(4096).decode("utf-8", "replace"))
                except UpdateError:
                    sha = ""
    return UpdateInfo(version=str(d.get("tag_name") or "").strip(), url=url, sha256=sha,
                      notes=str(d.get("body") or ""), page=str(d.get("html_url") or ""),
                      size=int(pick.get("size") or 0) if pick else 0)


def check(url: str, current: str = __version__):
    """Ask the update server. Returns an UpdateInfo if a newer version exists, else None."""
    data = _get_json(url)
    if isinstance(data, list):   # a GitHub "all releases" link: take the newest stable one
        data = next((r for r in data if isinstance(r, dict)
                     and not r.get("draft") and not r.get("prerelease")), {})
    if not isinstance(data, dict):
        raise UpdateError("The update server sent information the app cannot read.")
    info = _github_info(data) if "tag_name" in data else _manifest_info(data)
    if info is None or not info.version:
        return None
    if parse_version(info.version) is None:
        raise UpdateError("The update server sent an unreadable version number.")
    if is_prerelease(info.version) or not is_newer(info.version, current):
        return None
    return info


# -- installing ----------------------------------------------------------------------- #

def can_install_in_place() -> bool:
    """Only the installed Windows program can replace itself (not a run from source)."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def installable(info: UpdateInfo) -> bool:
    return can_install_in_place() and bool(info.url and info.sha256)


def download(info: UpdateInfo, progress=None, cancelled=None) -> Path:
    """Download the installer and verify its SHA-256. `progress(done, total)` is called as
    bytes arrive; `cancelled()` returning True aborts. Returns the verified file."""
    if not info.url or not info.sha256:
        raise UpdateError("This update has no checksum, so it cannot be installed automatically.")
    name = re.sub(r"[^0-9A-Za-z.]+", "", info.version)       # never trust names from the server
    name = re.sub(r"\.{2,}", ".", name).strip(".") or "update"
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    final = UPDATES_DIR / f"BookReader-Setup-{name}.exe"
    part = final.with_name(final.name + ".part")
    digest, done = hashlib.sha256(), 0
    try:
        with _open(info.url) as resp, open(part, "wb") as out:
            total = int(resp.headers.get("Content-Length") or info.size or 0)
            while True:
                if cancelled and cancelled():
                    raise UpdateError("Download cancelled.")
                chunk = resp.read(65536)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except UpdateError:
        part.unlink(missing_ok=True)
        raise
    except OSError as exc:
        part.unlink(missing_ok=True)
        raise UpdateError(f"The download failed ({exc}).") from exc
    if digest.hexdigest() != info.sha256.lower():
        part.unlink(missing_ok=True)
        raise UpdateError("The downloaded file does not match its checksum, so it was "
                          "discarded. Nothing was installed.")
    final.unlink(missing_ok=True)
    part.replace(final)
    return final


def launch_installer(path: Path):
    """Start the (verified) installer detached from this process. The caller then quits."""
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(path), *INSTALLER_ARGS], close_fds=True, creationflags=flags)


def cleanup():
    """Delete installers left over from earlier updates."""
    try:
        for f in UPDATES_DIR.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass   # still in use by a running installer
    except OSError:
        pass
