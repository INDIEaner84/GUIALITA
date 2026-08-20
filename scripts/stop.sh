#!/bin/bash
# GUIALITA - Stoppskript
# Beendet NUR die von GUIALITA gestarteten Prozesse.
# Ollama (SHARED SERVICE) wird NIEMALS beendet.

set -u

# Repository-Wurzel: aus GUIALITA_ROOT, sonst relativ zu diesem Skript.
GUIALITA_DIR="${GUIALITA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LOG_DIR="$GUIALITA_DIR/scripts/logs"
PID_FILE="$LOG_DIR/guialita.pid"

info()  { echo "[GUIALITA] $*"; }

info "=== GUIALITA Stop ==="

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null
        info "Backend-Prozess (PID $PID) beendet"
    else
        info "PID $PID laeuft nicht mehr"
    fi
    rm -f "$PID_FILE"
else
    info "Keine PID-Datei - suche GUIALITA-Backend-Prozesse"
    # Nur Prozesse mit backend/main.py aus dem GUIALITA-Verzeichnis beenden
    pids=$(pgrep -f "backend/main.py")
    for p in $pids; do
        cmdline=$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null)
        case "$cmdline" in
            *"$GUIALITA_DIR"*|*GUIALITA*) echo "$p" ;;
        esac
    done > /tmp/guialita_pids.$$
    pids=$(cat /tmp/guialita_pids.$$ 2>/dev/null); rm -f /tmp/guialita_pids.$$
    if [ -n "$pids" ]; then
        kill $pids 2>/dev/null
        info "Beendet: $pids"
    else
        info "Kein GUIALITA-Backend-Prozess gefunden"
    fi
fi

# Auf Beendigung warten
sleep 1

if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
    info "Hinweis: Port 8080 noch belegt - moeglicherweise anderer Prozess"
else
    info "Port 8080 frei"
fi

info "Ollama laeuft weiter (SHARED SERVICE - wird nicht beendet)"
info "=== GUIALITA gestoppt ==="
exit 0
