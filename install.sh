#!/usr/bin/env bash
# LangCoach Installer — macOS Apple Silicon (M1/M2/M3)
# Usage: curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/install.sh | bash
# Or:    bash install.sh

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────
GITHUB_OWNER="OWNER"          # <-- REPLACE with your GitHub username/org
GITHUB_REPO="REPO"            # <-- REPLACE with your GitHub repo name
INSTALL_DIR="$HOME/Applications/LangCoach"
APP_BUNDLE="/Applications/El Profesor.app"
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
step "Code source El Profesor"
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
step "Création d'El Profesor.app dans /Applications/"
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
  <string>El Profesor</string>
  <key>CFBundleDisplayName</key>
  <string>El Profesor</string>
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
  <string>El Profesor utilise le microphone pour reconnaître ta voix.</string>
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

ok "El Profesor.app créé dans /Applications/"

# ── Done ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}✅  El Profesor est installé !${RESET}"
echo -e "   Cherche-le dans ton ${BOLD}Launchpad${RESET} ou double-clique sur"
echo -e "   ${BOLD}/Applications/El Profesor.app${RESET}"
echo ""
echo -e "${YELLOW}Note :${RESET} Au premier lancement, Whisper (~500 MB) sera téléchargé"
echo -e "automatiquement. Compte 1-2 minutes de chargement."
echo ""
