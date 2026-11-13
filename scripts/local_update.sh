#!/usr/bin/env bash
# GUIALITA — lokales Update + vollständige Verifikation in einem Schritt
#
#   bash scripts/local_update.sh                # prüfen, starten, testen
#   bash scripts/local_update.sh --mock         # Chat-Pfad mit Test-Adapter prüfen
#                                               # (ohne GGUF-Modelle / ohne GPU)
#   bash scripts/local_update.sh --no-install   # Abhängigkeiten nicht anfassen
#   bash scripts/local_update.sh --keep-running # Backend nach dem Test laufen lassen
#   bash scripts/local_update.sh --pull         # vorher git pull (nur aktuelle Branch)
#
# Was das Skript tut:
#   1. virtuelle Umgebung sicherstellen (.venv oder GUIALITA_VENV)
#   2. Abhängigkeiten aus requirements.txt installieren (Kern zuerst, dann Rest)
#   3. Syntaxprüfung (compileall) + scripts/doctor.py
#   4. Backend starten und auf /health warten
#   5. scripts/run_all_tests.py ausführen (eine Suite = ein Lauf, keine Doppelzählung)
#   6. ehrliches Fazit: PASS / FAIL / NOT_EXECUTED getrennt
#
# Grenzen (bewusst):
#   - Ollama ist ein SHARED SERVICE: wird höchstens ERKANNT, nie gestartet,
#     gestoppt oder umkonfiguriert.
#   - Es wird nichts heruntergeladen außer Python-Paketen (kein Modell-Fetch).
#   - --mock ersetzt keine echte Runtime: es beweist den Chat-/Memory-/API-Pfad,
#     nicht die LLM-/STT-/TTS-Runtime.

set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1

USE_MOCK=0
DO_INSTALL=1
KEEP_RUNNING=0
DO_PULL=0

while [ $# -gt 0 ]; do
    case "$1" in
        --mock)         USE_MOCK=1; shift ;;
        --no-install)   DO_INSTALL=0; shift ;;
        --keep-running) KEEP_RUNNING=1; shift ;;
        --pull)         DO_PULL=1; shift ;;
        -h|--help)      sed -n '2,28p' "$0"; exit 0 ;;
        *) echo "[GUIALITA][FEHLER] Unbekannte Option: $1" >&2; exit 2 ;;
    esac
done

# .env laden, ohne bereits gesetzte Variablen zu überschreiben (wie start.sh).
if [ -f "$REPO/.env" ]; then
    while IFS='=' read -r key value; do
        case "$key" in ''|\#*) continue ;; esac
        key="$(echo "$key" | tr -d ' ')"
        [ -z "$key" ] && continue
        if [ -z "$(eval "echo \${$key:-}")" ]; then
            export "$key=$value"
        fi
    done < "$REPO/.env"
fi

VENV="${GUIALITA_VENV:-$REPO/.venv}"
PORT="${GUIALITA_PORT:-8080}"
HEALTH_URL="http://localhost:$PORT/health"
LOG_DIR="$REPO/scripts/logs"
UPDATE_LOG="$LOG_DIR/local_update_backend.log"
PID_FILE="$LOG_DIR/local_update.pid"
FAILED=0

info()  { printf '[GUIALITA] %s\n' "$*"; }
ok()    { printf '[GUIALITA]   \033[32m✓\033[0m %s\n' "$*"; }
warn()  { printf '[GUIALITA]   \033[33m!\033[0m %s\n' "$*"; }
bad()   { printf '[GUIALITA]   \033[31m✗\033[0m %s\n' "$*"; }
step()  { printf '\n[GUIALITA] === %s ===\n' "$*"; }

mkdir -p "$LOG_DIR"

# ---------- 0. optional: git pull (nur aktuelle Branch) ----------
if [ "$DO_PULL" -eq 1 ]; then
    step "0/6  git pull (aktuelle Branch)"
    BRANCH="$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    info "Branch: $BRANCH"
    if git -C "$REPO" pull --ff-only origin "$BRANCH"; then
        ok "pull erfolgreich"
    else
        bad "pull fehlgeschlagen — lokale Änderungen oder Divergenz prüfen"
        FAILED=1
    fi
fi

# ---------- 1. Python-Umgebung ----------
step "1/6  Python-Umgebung"
if [ ! -x "$VENV/bin/python" ]; then
    info "Erstelle venv: $VENV"
    python3 -m venv "$VENV" || { bad "venv konnte nicht erstellt werden"; exit 1; }
fi
PY="$VENV/bin/python"
ok "Python: $("$PY" -V 2>&1)  ($PY)"

# ---------- 2. Abhängigkeiten ----------
if [ "$DO_INSTALL" -eq 1 ]; then
    step "2/6  Abhängigkeiten"
    # Kern zuerst: damit Backend und Unit-Tests auch dann laufen, wenn eine
    # optionale/native Abhängigkeit (llama-cpp-python, sounddevice) nicht baut.
    CORE="fastapi uvicorn[standard] pydantic httpx PyYAML numpy pytest"
    if "$VENV/bin/pip" install --quiet --disable-pip-version-check $CORE; then
        ok "Kernpakete installiert"
    else
        bad "Kernpakete fehlgeschlagen — ohne sie läuft nichts"
        FAILED=1
    fi
    for extra in "llama-cpp-python" "sounddevice"; do
        if "$VENV/bin/pip" install --quiet --disable-pip-version-check "$extra" 2>/dev/null; then
            ok "$extra installiert"
        else
            warn "$extra nicht installiert (optional; echte Runtime fehlt dann)"
        fi
    done
else
    step "2/6  Abhängigkeiten (übersprungen: --no-install)"
fi

# ---------- 3. Syntax + Doctor ----------
step "3/6  Syntaxprüfung + Doctor"
if "$PY" -m compileall -q backend scripts tests; then
    ok "compileall: keine Syntaxfehler"
else
    bad "compileall: Syntaxfehler (siehe oben)"
    FAILED=1
fi
"$PY" scripts/doctor.py || warn "doctor.py meldet fehlende Modelle/Runtime (siehe oben)"

# ---------- 4. Backend starten ----------
step "4/6  Backend"
STARTED_BY_US=0
if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
    info "Backend läuft bereits auf Port $PORT — wird übernommen"
    warn "Ein laufendes Backend nutzt den Code vom Startzeitpunkt."
    warn "Für diesen Stand neu starten: bash scripts/start.sh --restart"
else
    STARTED_BY_US=1
    if [ "$USE_MOCK" -eq 1 ]; then
        export GUIALITA_MOCK_LLM=1
        info "Starte Backend mit Test-Adapter (GUIALITA_MOCK_LLM=1)"
    fi
    info "Starte Backend (Log: $UPDATE_LOG)"
    nohup "$PY" backend/main.py >> "$UPDATE_LOG" 2>&1 &
    echo $! > "$PID_FILE"
    for _ in $(seq 1 40); do
        curl -sf "$HEALTH_URL" > /dev/null 2>&1 && break
        sleep 1
    done
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        ok "Backend online: $HEALTH_URL"
    else
        bad "Backend nicht erreichbar — letzte Log-Zeilen:"
        tail -20 "$UPDATE_LOG" 2>/dev/null
        exit 1
    fi
fi

# Fähigkeiten kurz melden, damit das Fazit einordbar ist.
"$PY" - "$PORT" <<'PYEOF'
import json, sys, urllib.request
port = sys.argv[1]
def get(p):
    try:
        with urllib.request.urlopen(f"http://localhost:{port}{p}", timeout=10) as r:
            return json.load(r)
    except Exception as e:
        return {"error": str(e)}
d = get("/diagnostics")
caps = d.get("capabilities", {})
print("[GUIALITA]   Fähigkeiten: " + ", ".join(
    f"{k}={'ja' if v else 'nein'}" for k, v in caps.items()))
print(f"[GUIALITA]   voice-turn bereit: {d.get('ready_for_voice_turn')}")
print(f"[GUIALITA]   fehlend: {', '.join(d.get('missing_capabilities', [])) or '—'}")
PYEOF

# ---------- 5. Tests ----------
step "5/6  Testlauf (scripts/run_all_tests.py)"
"$PY" scripts/run_all_tests.py
TEST_RC=$?
if [ "$TEST_RC" -eq 0 ]; then
    ok "Testlauf ohne FAIL beendet (Exit 0)"
else
    bad "Testlauf mit FAIL beendet (Exit $TEST_RC)"
    FAILED=1
fi

# Unit-Schicht zusätzlich, weil sie kein Backend braucht (scripts/test.py).
step "5b/6  Unit-Schicht (scripts/test.py)"
if "$PY" scripts/test.py > "$LOG_DIR/unit.log" 2>&1; then
    ok "Unit-Schicht: $(tail -3 "$LOG_DIR/unit.log" | tr '\n' ' ')"
else
    bad "Unit-Schicht fehlgeschlagen (siehe $LOG_DIR/unit.log)"
    tail -20 "$LOG_DIR/unit.log"
    FAILED=1
fi

# ---------- 6. Aufräumen + Fazit ----------
step "6/6  Fazit"
if [ "$STARTED_BY_US" -eq 1 ] && [ "$KEEP_RUNNING" -eq 0 ]; then
    PID="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null
        info "Backend (PID $PID) beendet — es wurde nur für den Test gestartet"
    fi
    rm -f "$PID_FILE"
elif [ "$STARTED_BY_US" -eq 1 ]; then
    info "Backend läuft weiter (--keep-running): $HEALTH_URL"
    info "Beenden mit: bash scripts/stop.sh"
fi
info "Ollama wurde nicht angefasst (SHARED SERVICE, Port 11434)."

if [ "$FAILED" -eq 0 ]; then
    info "ERGEBNIS: lokales Update verifiziert — keine FAILs."
    info "Achtung: NOT_EXECUTED-Suiten sind nicht bestanden, sie konnten wegen"
    info "fehlender Modelle/Runtime/Hardware nicht ausgeführt werden."
    exit 0
else
    info "ERGEBNIS: es gibt Fehler — Ausgabe oben prüfen."
    exit 1
fi
