#!/bin/bash
# GUIALITA - Desktop-Starter installieren
# Installiert GUIALITA.desktop in ~/.local/share/applications/

set -u

GUIALITA_DIR="/media/hz/_Ext_Seagat/GUIALITA"
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
