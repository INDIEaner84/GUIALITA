#!/bin/bash
# GUIALITA - Desktop-Starter installieren
# Installiert GUIALITA.desktop in ~/.local/share/applications/

set -u

# Repository-Wurzel: aus GUIALITA_ROOT, sonst relativ zu diesem Skript.
GUIALITA_DIR="${GUIALITA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
APPS_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APPS_DIR/GUIALITA.desktop"

mkdir -p "$APPS_DIR"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=GUIALITA
Comment=Local AI Assistant
Exec=bash "$GUIALITA_DIR/scripts/start.sh"
Icon=utilities-terminal
Terminal=false
Categories=Utility;Development;ArtificialIntelligence;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"
echo "[GUIALITA] Desktop-Eintrag installiert: $DESKTOP_FILE"
echo "[GUIALITA] GUIALITA erscheint im Anwendungsmenue (Kategorie: Entwicklung)"
exit 0
