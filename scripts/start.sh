#!/bin/bash
# GUIALITA - Startskript
# Startet Backend, wartet auf /health, prueft Primaermodell, oeffnet Browser.
# Ollama wird nur ERKANNT, niemals beendet oder konfiguriert (SHARED SERVICE).

set -u

# Repository-Wurzel: aus GUIALITA_ROOT, sonst relativ zu diesem Skript.
GUIALITA_DIR="${GUIALITA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# Python-Umgebung: GUIALITA_VENV, sonst .venv im Repo, sonst System-Python.
VENV="${GUIALITA_VENV:-$GUIALITA_DIR/.venv}"
PORT=8080
LOG_DIR="$GUIALITA_DIR/scripts/logs"
BACKEND_LOG="$LOG_DIR/backend.log"
PID_FILE="$LOG_DIR/guialita.pid"
HEALTH_URL="http://localhost:$PORT/health"
FRONTEND_URL="http://localhost:$PORT"

mkdir -p "$LOG_DIR"

info()  { echo "[GUIALITA] $*"; }
error() { echo "[GUIALITA][FEHLER] $*" >&2; }

info "=== GUIALITA Start ==="

# ---------- 1. Umgebung pruefen ----------
if [ -x "$VENV/bin/python" ]; then
    PYTHON="$VENV/bin/python"
elif command -v python3 > /dev/null 2>&1; then
    info "Kein Venv unter $VENV - nutze python3 aus \$PATH"
    PYTHON="$(command -v python3)"
else
    error "Weder Venv ($VENV) noch python3 gefunden."
    error "Erstelle eine Umgebung: python3 -m venv \"$VENV\""
    error "und installiere: \"$VENV/bin/pip\" install -r \"$GUIALITA_DIR/requirements.txt\""
    exit 1
fi

# ---------- 2. Modell vorhanden? ----------
MODEL_FILE="${GUIALITA_MODEL_ROOT:-$GUIALITA_DIR/models}/lfm-vision-3b/LFM2.5-VL-3B-Q4_K_M.gguf"
if [ ! -f "$MODEL_FILE" ]; then
    info "Hinweis: LFM-Vision-Modell fehlt noch - wird im Hintergrund geladen"
fi

# ---------- 3. Backend starten (nur wenn nicht bereits aktiv) ----------
if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
    info "Backend laeuft bereits auf $HEALTH_URL"
else
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            info "Alten Backend-Prozess (PID $OLD_PID) uebrig - beende ihn"
            kill "$OLD_PID" 2>/dev/null
            sleep 1
        fi
        rm -f "$PID_FILE"
    fi

    info "Starte Backend auf Port $PORT ..."
    cd "$GUIALITA_DIR"
    nohup "$PYTHON" backend/main.py >> "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$PID_FILE"
    info "Backend-PID: $BACKEND_PID (Log: $BACKEND_LOG)"
fi

# ---------- 4. Auf /health warten ----------
info "Warte auf /health ..."
HEALTHY=0
for i in $(seq 1 60); do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        HEALTHY=1
        break
    fi
    sleep 1
done

if [ "$HEALTHY" -eq 0 ]; then
    error "Backend wurde nicht innerhalb von 60s verfuegbar."
    error "Letzte Log-Zeilen:"
    tail -20 "$BACKEND_LOG" 2>/dev/null
    exit 1
fi
info "Backend online: $HEALTH_URL"

# ---------- 5. Primaermodell pruefen ----------
PRIMARY=$("$PYTHON" - "$PORT" <<'PYEOF'
import json, sys, urllib.request
port = sys.argv[1]
try:
    with urllib.request.urlopen(f"http://localhost:{port}/models", timeout=5) as r:
        data = json.load(r)
    models = [m for m in data.get("models", []) if m.get("available")]
    print(models[0]["id"] if models else "NONE")
except Exception as e:
    print("NONE")
PYEOF
)
if [ "$PRIMARY" != "NONE" ]; then
    info "Primaermodell verfuegbar: $PRIMARY"
else
    info "Kein Modell verfuegbar - Modell-Downloads laufen evtl. noch (siehe scripts/download_models.sh)"
fi

# ---------- 6. Ollama-Status (nur ERKENNEN, nicht beenden) ----------
if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    info "Ollama erkannt (SHARED SERVICE, Port 11434) - wird nicht veraendert"
else
    info "Ollama nicht erreichbar - GUIALITA nutzt llama-cpp-python (dediziert)"
fi

# ---------- 7. Browser oeffnen ----------
info "Oeffne Browser: $FRONTEND_URL"
sleep 1
xdg-open "$FRONTEND_URL" > /dev/null 2>&1 || sensible-browser "$FRONTEND_URL" > /dev/null 2>&1 || true

info "=== GUIALITA laeuft auf $FRONTEND_URL ==="
info "Beenden: scripts/stop.sh (beendet NUR GUIALITA-Prozesse)"
exit 0
