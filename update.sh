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
