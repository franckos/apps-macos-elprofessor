"""
LangCoach — Updater
Checks GitHub Releases for a newer version and triggers update.sh.
"""
import json
import logging
import os
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────
GITHUB_OWNER = "OWNER"   # <-- REPLACE with your GitHub username/org
GITHUB_REPO  = "REPO"    # <-- REPLACE with your GitHub repo name

# Path to version.txt — resolved relative to this file's location
# core/updater.py → langcoach/ → MacOS/ → version.txt
_VERSION_FILE = Path(__file__).parent.parent.parent / "version.txt"
_UPDATE_SCRIPT = Path.home() / "Applications" / "LangCoach" / "update.sh"


@dataclass
class UpdateInfo:
    local_version: str
    latest_version: str
    release_url: str
    update_available: bool


def get_local_version(path: Optional[Path] = None) -> str:
    """Read version from version.txt. Returns '0.0.0' if missing."""
    p = path or _VERSION_FILE
    try:
        return p.read_text().strip()
    except FileNotFoundError:
        log.warning("version.txt not found at %s", p)
        return "0.0.0"


def compare_versions(local: str, latest: str) -> bool:
    """Return True if latest > local (semver, integers only)."""
    def parts(v: str):
        return tuple(int(x) for x in v.split(".")[:3])
    return parts(latest) > parts(local)


def fetch_latest_release(
    owner: str = GITHUB_OWNER,
    repo: str = GITHUB_REPO,
) -> Optional[UpdateInfo]:
    """
    Query GitHub Releases API for the latest release.
    Returns UpdateInfo on success, None on network/parse error.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "LangCoach"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        tag = data.get("tag_name", "")
        latest = tag.lstrip("v")
        local = get_local_version()
        return UpdateInfo(
            local_version=local,
            latest_version=latest,
            release_url=data.get("html_url", ""),
            update_available=compare_versions(local, latest),
        )
    except Exception as e:
        log.warning("Failed to fetch latest release: %s", e)
        return None


def run_update() -> bool:
    """
    Open a new Terminal window that runs update.sh.
    Returns True if Terminal was launched successfully.
    """
    script = str(_UPDATE_SCRIPT)
    if not _UPDATE_SCRIPT.exists():
        log.error("update.sh not found at %s", script)
        return False
    # open -a Terminal runs update.sh in a new visible Terminal window
    try:
        subprocess.Popen(
            ["open", "-a", "Terminal", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        log.error("Failed to launch Terminal for update: %s", e)
        return False
