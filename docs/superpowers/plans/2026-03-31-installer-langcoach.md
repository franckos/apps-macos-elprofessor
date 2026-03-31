# LangCoach Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an `install.sh` that turns LangCoach into a double-clickable macOS app installable by non-technical users, plus a "Vérifier les mises à jour" button in the Settings panel.

**Architecture:** An idempotent shell script clones the repo, sets up the Python venv, pulls the Ollama model, and creates a native `.app` bundle in `/Applications/`. A separate `updater.py` module handles GitHub Releases version checking from within the PyQt6 UI, and `update.sh` handles pulling new code.

**Tech Stack:** bash, macOS native `.app` bundle format (Info.plist + shell launcher), Python 3.11 (brew), PyQt6, `urllib.request` (stdlib), `iconutil` (macOS built-in)

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `install.sh` | Create | Full idempotent installer — Homebrew, portaudio, ollama, venv, pip, model pull, .app creation |
| `update.sh` | Create | Fast updater — git pull + pip install only |
| `version.txt` | Create | Current semver string e.g. `1.0.0` |
| `assets/LangCoach.icns` | Create (manual step) | macOS app icon in .icns format |
| `langcoach/core/updater.py` | Create | Version check via GitHub API + launch update.sh |
| `langcoach/tests/test_updater.py` | Create | Unit tests for updater logic (mocked HTTP) |
| `langcoach/ui/settings_panel.py` | Modify | Add "App" section with version label + update button |

> **Important:** Before starting, replace every occurrence of `OWNER/REPO` in `install.sh` and `update.sh` with the actual GitHub path once the repo is published (e.g. `quantelys/langcoach`).

---

## Task 1: version.txt

**Files:**
- Create: `version.txt`

- [ ] **Step 1: Create version.txt at repo root**

```
1.0.0
```

Save as `version.txt` (no trailing newline, no quotes) at the root of the MacOS directory (alongside `langcoach/`, `install.sh`, etc.).

- [ ] **Step 2: Commit**

```bash
git add version.txt
git commit -m "chore: add version.txt (1.0.0)"
```

---

## Task 2: install.sh

**Files:**
- Create: `install.sh`

- [ ] **Step 1: Create install.sh**

```bash
#!/usr/bin/env bash
# LangCoach Installer — macOS Apple Silicon (M1/M2/M3)
# Usage: curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/install.sh | bash
# Or:    bash install.sh

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────
GITHUB_OWNER="OWNER"          # <-- REPLACE with your GitHub username/org
GITHUB_REPO="REPO"            # <-- REPLACE with your GitHub repo name
INSTALL_DIR="$HOME/Applications/LangCoach"
APP_BUNDLE="/Applications/LangCoach.app"
PYTHON_VERSION="3.11"

# ── Colors ────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

step()  { echo -e "\n${BLUE}▶${RESET} ${BOLD}$1${RESET}"; }
ok()    { echo -e "  ${GREEN}✓${RESET} $1"; }
warn()  { echo -e "  ${YELLOW}⚠${RESET}  $1"; }
die()   { echo -e "\n${RED}✗ Erreur : $1${RESET}\n"; exit 1; }

# ── Step 1: Verify macOS + Apple Silicon ──────────────────────
step "Vérification macOS + Apple Silicon"
[[ "$(uname -s)" == "Darwin" ]] || die "Ce script est réservé à macOS."
[[ "$(uname -m)" == "arm64"  ]] || die "Apple Silicon (M1/M2/M3) requis. Intel non supporté."
ok "macOS Apple Silicon détecté"

# ── Step 2: Homebrew ──────────────────────────────────────────
step "Homebrew"
if ! command -v brew &>/dev/null; then
  echo "  Installation de Homebrew (vous devrez peut-être entrer votre mot de passe)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Add brew to PATH for the rest of this script (Apple Silicon default path)
  eval "$(/opt/homebrew/bin/brew shellenv)"
else
  ok "Homebrew déjà installé"
fi
# Ensure brew is on PATH even if already installed
eval "$(brew shellenv 2>/dev/null || true)"

# ── Step 3: PortAudio ─────────────────────────────────────────
step "PortAudio"
if brew list portaudio &>/dev/null; then
  ok "PortAudio déjà installé"
else
  brew install portaudio
  ok "PortAudio installé"
fi

# ── Step 4: Python 3.11 ───────────────────────────────────────
step "Python $PYTHON_VERSION"
PYTHON_BIN="$(brew --prefix)/bin/python$PYTHON_VERSION"
if brew list python@$PYTHON_VERSION &>/dev/null; then
  ok "Python $PYTHON_VERSION déjà installé"
else
  brew install python@$PYTHON_VERSION
  ok "Python $PYTHON_VERSION installé"
fi
[[ -x "$PYTHON_BIN" ]] || die "python$PYTHON_VERSION introuvable après installation."

# ── Step 5: Ollama ────────────────────────────────────────────
step "Ollama"
if brew list ollama &>/dev/null; then
  ok "Ollama déjà installé"
else
  brew install ollama
  ok "Ollama installé"
fi

# ── Step 6: Clone or update repo ─────────────────────────────
step "Code source LangCoach"
REPO_URL="https://github.com/$GITHUB_OWNER/$GITHUB_REPO.git"
if [[ -d "$INSTALL_DIR/.git" ]]; then
  ok "Répertoire existant — mise à jour"
  git -C "$INSTALL_DIR" pull --ff-only
else
  mkdir -p "$HOME/Applications"
  git clone "$REPO_URL" "$INSTALL_DIR"
  ok "Repo cloné dans $INSTALL_DIR"
fi

# ── Step 7: Python venv + dependencies ───────────────────────
step "Environnement Python (venv + dépendances)"
VENV_DIR="$INSTALL_DIR/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  ok "venv créé"
else
  ok "venv existant"
fi

PIP="$VENV_DIR/bin/pip"
"$PIP" install --upgrade pip --quiet
"$PIP" install -r "$INSTALL_DIR/langcoach/requirements.txt" --quiet
ok "Dépendances Python installées"

# Kokoro TTS (belle voix)
if "$VENV_DIR/bin/python" -c "import kokoro" 2>/dev/null; then
  ok "Kokoro déjà installé"
else
  echo "  Installation de Kokoro TTS..."
  "$PIP" install kokoro soundfile --quiet
  ok "Kokoro installé"
fi

# ── Step 8: Ollama model (llama3.1:8b, ~4.7 GB) ──────────────
step "Modèle Ollama (llama3.1:8b — ~4.7 GB, peut prendre 5-15 min)"

# Start ollama serve in background if not already running
if ! pgrep -x "ollama" &>/dev/null; then
  ollama serve &>/dev/null &
  sleep 3  # give it time to start
fi

if ollama list 2>/dev/null | grep -q "llama3.1:8b"; then
  ok "llama3.1:8b déjà téléchargé"
else
  echo "  Téléchargement en cours... (la progression s'affiche ci-dessous)"
  ollama pull llama3.1:8b
  ok "llama3.1:8b téléchargé"
fi

# ── Step 9: Create /Applications/LangCoach.app ───────────────
step "Création de LangCoach.app dans /Applications/"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"

mkdir -p "$APP_MACOS" "$APP_RESOURCES"

# Info.plist
cat > "$APP_CONTENTS/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>LangCoach</string>
  <key>CFBundleDisplayName</key>
  <string>LangCoach</string>
  <key>CFBundleIdentifier</key>
  <string>com.quantelys.langcoach</string>
  <key>CFBundleVersion</key>
  <string>1.0.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
  <key>CFBundleExecutable</key>
  <string>LangCoach</string>
  <key>CFBundleIconFile</key>
  <string>LangCoach</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSMicrophoneUsageDescription</key>
  <string>LangCoach utilise le microphone pour reconnaître ta voix.</string>
</dict>
</plist>
PLIST

# Shell launcher
cat > "$APP_MACOS/LangCoach" <<LAUNCHER
#!/usr/bin/env bash
# LangCoach launcher
INSTALL_DIR="\$HOME/Applications/LangCoach"
VENV="\$INSTALL_DIR/.venv"

# Activate venv
source "\$VENV/bin/activate"

# Start Ollama in background if not running
if ! pgrep -x "ollama" &>/dev/null; then
  /opt/homebrew/bin/ollama serve &>/dev/null &
  sleep 2
fi

# Launch app
cd "\$INSTALL_DIR/langcoach"
exec "\$VENV/bin/python" main.py
LAUNCHER

chmod +x "$APP_MACOS/LangCoach"

# Copy icon if it exists
ICON_SRC="$INSTALL_DIR/assets/LangCoach.icns"
if [[ -f "$ICON_SRC" ]]; then
  cp "$ICON_SRC" "$APP_RESOURCES/LangCoach.icns"
  ok "Icône copiée"
else
  warn "Aucune icône trouvée dans assets/LangCoach.icns — l'app utilisera l'icône par défaut"
fi

# Refresh Launchpad / Finder icon cache
touch "$APP_BUNDLE"

ok "LangCoach.app créé dans /Applications/"

# ── Done ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✅  LangCoach est installé !${RESET}"
echo -e "   Cherche-le dans ton ${BOLD}Launchpad${RESET} ou double-clique sur"
echo -e "   ${BOLD}/Applications/LangCoach.app${RESET}"
echo ""
echo -e "${YELLOW}Note :${RESET} Au premier lancement, Whisper (~500 MB) sera téléchargé"
echo -e "automatiquement. Compte 1-2 minutes de chargement."
echo ""
```

- [ ] **Step 2: Make executable and verify syntax**

```bash
chmod +x install.sh
bash -n install.sh
```

Expected: no output (no syntax errors).

- [ ] **Step 3: Commit**

```bash
git add install.sh
git commit -m "feat: add install.sh — idempotent macOS installer"
```

---

## Task 3: update.sh

**Files:**
- Create: `update.sh`

- [ ] **Step 1: Create update.sh**

```bash
#!/usr/bin/env bash
# LangCoach Updater
# Called by the app when user clicks "Mettre à jour"
# Usage: bash ~/Applications/LangCoach/update.sh

set -euo pipefail

INSTALL_DIR="$HOME/Applications/LangCoach"
VENV_DIR="$INSTALL_DIR/.venv"

GREEN='\033[0;32m'; BLUE='\033[0;34m'; BOLD='\033[1m'; RESET='\033[0m'

step() { echo -e "\n${BLUE}▶${RESET} ${BOLD}$1${RESET}"; }
ok()   { echo -e "  ${GREEN}✓${RESET} $1"; }

step "Mise à jour du code source"
git -C "$INSTALL_DIR" pull --ff-only
ok "Code à jour"

step "Mise à jour des dépendances Python"
"$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/langcoach/requirements.txt" --quiet
ok "Dépendances à jour"

# Regenerate .app launcher in case it changed
step "Régénération du launcher .app"
APP_MACOS="/Applications/LangCoach.app/Contents/MacOS"
if [[ -d "$APP_MACOS" ]]; then
  cat > "$APP_MACOS/LangCoach" <<LAUNCHER
#!/usr/bin/env bash
INSTALL_DIR="\$HOME/Applications/LangCoach"
VENV="\$INSTALL_DIR/.venv"
source "\$VENV/bin/activate"
if ! pgrep -x "ollama" &>/dev/null; then
  /opt/homebrew/bin/ollama serve &>/dev/null &
  sleep 2
fi
cd "\$INSTALL_DIR/langcoach"
exec "\$VENV/bin/python" main.py
LAUNCHER
  chmod +x "$APP_MACOS/LangCoach"
  ok "Launcher régénéré"
fi

echo ""
echo -e "${GREEN}${BOLD}✅  Mise à jour terminée !${RESET}"
echo -e "   Relance LangCoach depuis le Launchpad."
echo ""
```

- [ ] **Step 2: Make executable and verify syntax**

```bash
chmod +x update.sh
bash -n update.sh
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add update.sh
git commit -m "feat: add update.sh — incremental updater"
```

---

## Task 4: App icon (manual step — assets/LangCoach.icns)

**Files:**
- Create: `assets/LangCoach.icns` (generated from PNG)

This is a manual asset creation step using macOS built-in tools. No code is written here.

- [ ] **Step 1: Prepare a 1024×1024 PNG source image**

Place your app icon source (1024×1024 pixels, PNG) at:
```
/tmp/langcoach_icon.png
```

If you don't have one yet, skip this task — the installer will still work, just without a custom icon. You can add it later.

- [ ] **Step 2: Generate the .icns file using iconutil**

```bash
# Create the iconset directory
mkdir -p /tmp/LangCoach.iconset

# Generate all required sizes from the 1024x1024 source
sips -z 16 16     /tmp/langcoach_icon.png --out /tmp/LangCoach.iconset/icon_16x16.png
sips -z 32 32     /tmp/langcoach_icon.png --out /tmp/LangCoach.iconset/icon_16x16@2x.png
sips -z 32 32     /tmp/langcoach_icon.png --out /tmp/LangCoach.iconset/icon_32x32.png
sips -z 64 64     /tmp/langcoach_icon.png --out /tmp/LangCoach.iconset/icon_32x32@2x.png
sips -z 128 128   /tmp/langcoach_icon.png --out /tmp/LangCoach.iconset/icon_128x128.png
sips -z 256 256   /tmp/langcoach_icon.png --out /tmp/LangCoach.iconset/icon_128x128@2x.png
sips -z 256 256   /tmp/langcoach_icon.png --out /tmp/LangCoach.iconset/icon_256x256.png
sips -z 512 512   /tmp/langcoach_icon.png --out /tmp/LangCoach.iconset/icon_256x256@2x.png
sips -z 512 512   /tmp/langcoach_icon.png --out /tmp/LangCoach.iconset/icon_512x512.png
sips -z 1024 1024 /tmp/langcoach_icon.png --out /tmp/LangCoach.iconset/icon_512x512@2x.png

# Convert iconset to .icns
iconutil -c icns /tmp/LangCoach.iconset -o assets/LangCoach.icns
```

Expected: `assets/LangCoach.icns` is created (~200 KB).

- [ ] **Step 3: Commit**

```bash
git add assets/LangCoach.icns
git commit -m "feat: add LangCoach app icon (.icns)"
```

> After adding the icon, re-run `install.sh` (or just the `.app` creation step) to copy it into the bundle.

---

## Task 5: langcoach/core/updater.py

**Files:**
- Create: `langcoach/core/updater.py`
- Create: `langcoach/tests/test_updater.py`

- [ ] **Step 1: Write the failing tests**

Create `langcoach/tests/test_updater.py`:

```python
"""Tests for core/updater.py"""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Allow running from langcoach/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.updater import (
    compare_versions,
    fetch_latest_release,
    get_local_version,
    UpdateInfo,
)


# ── compare_versions ──────────────────────────────────────────

def test_compare_newer():
    assert compare_versions("1.0.0", "1.1.0") is True

def test_compare_same():
    assert compare_versions("1.0.0", "1.0.0") is False

def test_compare_older():
    assert compare_versions("2.0.0", "1.9.9") is False

def test_compare_patch():
    assert compare_versions("1.0.0", "1.0.1") is True

def test_compare_major():
    assert compare_versions("1.9.9", "2.0.0") is True


# ── get_local_version ─────────────────────────────────────────

def test_get_local_version_reads_file(tmp_path):
    version_file = tmp_path / "version.txt"
    version_file.write_text("2.3.1\n")
    assert get_local_version(version_file) == "2.3.1"

def test_get_local_version_missing_file(tmp_path):
    assert get_local_version(tmp_path / "nope.txt") == "0.0.0"

def test_get_local_version_strips_whitespace(tmp_path):
    f = tmp_path / "version.txt"
    f.write_text("  1.2.3  \n")
    assert get_local_version(f) == "1.2.3"


# ── fetch_latest_release ──────────────────────────────────────

def _mock_urlopen(tag_name: str):
    """Returns a context manager that yields a fake GitHub API response."""
    payload = json.dumps({"tag_name": tag_name, "html_url": "https://example.com"}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = payload
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp

def test_fetch_latest_release_returns_update_info():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen("v1.5.0")):
        info = fetch_latest_release("owner", "repo")
    assert info.latest_version == "1.5.0"
    assert info.release_url == "https://example.com"

def test_fetch_latest_release_strips_v_prefix():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen("v2.0.0")):
        info = fetch_latest_release("owner", "repo")
    assert info.latest_version == "2.0.0"

def test_fetch_latest_release_no_prefix():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen("3.1.0")):
        info = fetch_latest_release("owner", "repo")
    assert info.latest_version == "3.1.0"

def test_fetch_latest_release_network_error():
    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        info = fetch_latest_release("owner", "repo")
    assert info is None
```

- [ ] **Step 2: Run tests to confirm they fail (module not yet created)**

```bash
cd langcoach
python -m pytest tests/test_updater.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'core.updater'`

- [ ] **Step 3: Create langcoach/core/updater.py**

```python
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
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
cd langcoach
python -m pytest tests/test_updater.py -v
```

Expected output (all green):
```
tests/test_updater.py::test_compare_newer PASSED
tests/test_updater.py::test_compare_same PASSED
tests/test_updater.py::test_compare_older PASSED
tests/test_updater.py::test_compare_patch PASSED
tests/test_updater.py::test_compare_major PASSED
tests/test_updater.py::test_get_local_version_reads_file PASSED
tests/test_updater.py::test_get_local_version_missing_file PASSED
tests/test_updater.py::test_get_local_version_strips_whitespace PASSED
tests/test_updater.py::test_fetch_latest_release_returns_update_info PASSED
tests/test_updater.py::test_fetch_latest_release_strips_v_prefix PASSED
tests/test_updater.py::test_fetch_latest_release_no_prefix PASSED
tests/test_updater.py::test_fetch_latest_release_network_error PASSED
```

- [ ] **Step 5: Commit**

```bash
git add langcoach/core/updater.py langcoach/tests/test_updater.py
git commit -m "feat: add updater module with GitHub Releases version check"
```

---

## Task 6: Settings panel — "Mises à jour" section

**Files:**
- Modify: `langcoach/ui/settings_panel.py`

The settings panel uses a callback pattern (`on_settings_changed`, `on_close`). We'll add `on_update_requested` for when the user clicks "Mettre à jour", keeping the same pattern.

- [ ] **Step 1: Add `on_update_requested` callback and `_check_in_progress` flag to `__init__`**

In `langcoach/ui/settings_panel.py`, in `SettingsPanel.__init__`, after the existing `self.on_close = None` line, add:

```python
        self.on_update_requested = None  # callback() → called when user confirms update
        self._check_in_progress = False
```

- [ ] **Step 2: Add the "App" section to the layout, after `layout.addStretch()`**

In the `__init__` method, replace `layout.addStretch()` with:

```python
        layout.addStretch()

        layout.addWidget(self._section("⬆  App"))
        layout.addWidget(self._build_update_section())
```

- [ ] **Step 3: Add `_build_update_section` method**

Add this method to `SettingsPanel`, before the `_update` method at the bottom of the class:

```python
    def _build_update_section(self) -> QWidget:
        from core.updater import fetch_latest_release, run_update, get_local_version

        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        local_ver = get_local_version()
        version_label = QLabel(f"Version installée : {local_ver}")
        version_label.setFont(QFont(T["font_body"], T["font_size_xs"]))
        version_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
        layout.addWidget(version_label)

        status_label = QLabel("")
        status_label.setFont(QFont(T["font_body"], T["font_size_xs"]))
        status_label.setStyleSheet(f"color: {T['text_secondary']}; background: transparent;")
        status_label.setWordWrap(True)
        layout.addWidget(status_label)

        btn = QPushButton("Vérifier les mises à jour")
        btn.setFixedHeight(36)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['bg_card']};
                color: {T['text_primary']};
                border: 1px solid {T['border']};
                border-radius: {T['radius_md']}px;
                padding: 0 16px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
            }}
            QPushButton:hover {{
                border-color: {T['accent']};
                background-color: {T['accent_soft']};
                color: {T['accent']};
            }}
            QPushButton:disabled {{
                color: {T['text_muted']};
            }}
        """)
        layout.addWidget(btn)

        update_btn = QPushButton("⬆  Mettre à jour")
        update_btn.setFixedHeight(36)
        update_btn.setVisible(False)
        update_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T['accent']};
                color: #ffffff;
                border: none;
                border-radius: {T['radius_md']}px;
                padding: 0 16px;
                font-size: {T['font_size_sm']}px;
                font-family: '{T['font_body']}';
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {T['accent']};
                opacity: 0.9;
            }}
        """)
        layout.addWidget(update_btn)

        def on_check():
            if self._check_in_progress:
                return
            self._check_in_progress = True
            btn.setEnabled(False)
            btn.setText("Vérification…")
            status_label.setText("")
            update_btn.setVisible(False)

            # Run in background thread to avoid blocking UI
            import threading
            def _check():
                info = fetch_latest_release()
                # Schedule UI update on main thread via a single-shot QTimer
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: _update_ui(info))

            def _update_ui(info):
                self._check_in_progress = False
                btn.setEnabled(True)
                btn.setText("Vérifier les mises à jour")
                if info is None:
                    status_label.setText("Impossible de vérifier (pas de connexion ?)")
                    status_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")
                elif info.update_available:
                    status_label.setText(f"Version {info.latest_version} disponible !")
                    status_label.setStyleSheet(f"color: {T['accent']}; background: transparent;")
                    update_btn.setVisible(True)
                    update_btn.setProperty("release_url", info.release_url)
                else:
                    status_label.setText(f"Vous avez la dernière version ({info.local_version}).")
                    status_label.setStyleSheet(f"color: {T['text_muted']}; background: transparent;")

            threading.Thread(target=_check, daemon=True).start()

        def on_update():
            run_update()
            if self.on_update_requested:
                self.on_update_requested()

        btn.clicked.connect(on_check)
        update_btn.clicked.connect(on_update)
        return w
```

- [ ] **Step 4: Manual smoke test**

```bash
cd langcoach
python main.py
```

1. Open Settings (press `S` or click "⚙ Paramètres")
2. Scroll to the bottom — verify "⬆  App" section is visible with version label and button
3. Click "Vérifier les mises à jour" — button should say "Vérification…" then return a result
4. If GITHUB_OWNER/GITHUB_REPO are still placeholders, you'll see "Impossible de vérifier" — that's expected

- [ ] **Step 5: Commit**

```bash
git add langcoach/ui/settings_panel.py
git commit -m "feat: add 'Vérifier les mises à jour' section in Settings panel"
```

---

## Task 7: Wire GITHUB_OWNER/GITHUB_REPO — final configuration

Once the GitHub repo is created and code pushed, replace the two placeholder values in two files:

**Files:**
- Modify: `install.sh`
- Modify: `langcoach/core/updater.py`

- [ ] **Step 1: Update install.sh**

In `install.sh`, replace:
```bash
GITHUB_OWNER="OWNER"
GITHUB_REPO="REPO"
```
with:
```bash
GITHUB_OWNER="your-github-username"   # e.g. "quantelys"
GITHUB_REPO="your-repo-name"          # e.g. "langcoach"
```

- [ ] **Step 2: Update langcoach/core/updater.py**

In `langcoach/core/updater.py`, replace:
```python
GITHUB_OWNER = "OWNER"
GITHUB_REPO  = "REPO"
```
with:
```python
GITHUB_OWNER = "your-github-username"
GITHUB_REPO  = "your-repo-name"
```

- [ ] **Step 3: Commit**

```bash
git add install.sh langcoach/core/updater.py
git commit -m "chore: set GitHub repo coordinates for installer and updater"
```

---

## Task 8: End-to-end manual test (on a fresh machine or fresh user account)

This task has no code — it's the acceptance test. Run it on a machine that doesn't have LangCoach installed.

- [ ] **Step 1: Run the installer**

```bash
curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/install.sh | bash
```

Expected sequence of green checkmarks:
```
▶ Vérification macOS + Apple Silicon
  ✓ macOS Apple Silicon détecté
▶ Homebrew
  ✓ Homebrew déjà installé   (or installs it)
▶ PortAudio
  ✓ PortAudio installé
▶ Python 3.11
  ✓ Python 3.11 installé
▶ Ollama
  ✓ Ollama installé
▶ Code source LangCoach
  ✓ Repo cloné dans ~/Applications/LangCoach
▶ Environnement Python (venv + dépendances)
  ✓ Dépendances Python installées
  ✓ Kokoro installé
▶ Modèle Ollama (llama3.1:8b — ~4.7 GB, peut prendre 5-15 min)
  ✓ llama3.1:8b téléchargé
▶ Création de LangCoach.app dans /Applications/
  ✓ LangCoach.app créé dans /Applications/

✅  LangCoach est installé !
```

- [ ] **Step 2: Launch from Launchpad or Finder**

Double-click `LangCoach` in Launchpad or `/Applications/LangCoach.app`.

Expected:
- App opens normally
- Ollama starts in background if not running
- STT/TTS models download on first use (progress shown in terminal logs)

- [ ] **Step 3: Test idempotency — run installer again**

```bash
bash ~/Applications/LangCoach/install.sh
```

Expected: All steps show "déjà installé" / "déjà téléchargé" — nothing reinstalled.

- [ ] **Step 4: Test update flow**

- Open Settings → scroll to bottom
- Click "Vérifier les mises à jour"
- If a new version exists: "Version X.X disponible !" appears + "Mettre à jour" button
- Click "Mettre à jour" → Terminal window opens, runs `update.sh`, shows progress

---

## Notes

**Python version:** The installer forces Python 3.11 via Homebrew (`/opt/homebrew/bin/python3.11`). This avoids issues with the macOS system Python (which varies between 3.9–3.12 depending on macOS version).

**First launch is slow:** Whisper and HuggingFace models (~500 MB–1 GB) download to `~/.cache/huggingface/` on first use. This is intentional — it avoids bloating the install script.

**Icon:** The `.icns` file is binary and should be committed directly. Git handles binary files fine for assets of this size (~200 KB).

**Gatekeeper warning:** On first launch, macOS may show "LangCoach cannot be opened because it is from an unidentified developer." The user must right-click → Open → Open to bypass this. This is expected for unsigned apps distributed outside the App Store. Adding a note about this in the README is recommended.
