#!/usr/bin/env bash
# GUIALITA — lokale Einrichtung
#
# Sucht auf dieser Maschine nach Modellen, Runtime und whisper.cpp und
# schreibt daraus eine `.env`. Danach ist GUIALITA startklar, ohne dass
# irgendein Pfad im Repository maschinenspezifisch sein muss.
#
#   bash scripts/setup_local.sh                    # suchen und .env schreiben
#   bash scripts/setup_local.sh --dry-run          # nur zeigen, nichts schreiben
#   bash scripts/setup_local.sh --hint /pfad/dir   # zusätzlichen Suchort angeben
#
# Es wird nichts kopiert, verschoben oder gelöscht. Eine vorhandene `.env`
# wird nur nach Rückfrage überschrieben.

set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO/.env"
DRY_RUN=0
HINTS=()

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --hint)    HINTS+=("$2"); shift 2 ;;
        -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
        *) echo "Unbekannte Option: $1"; exit 2 ;;
    esac
done

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
miss() { printf '  \033[33m·\033[0m %s\n' "$*"; }
info() { printf '  %s\n' "$*"; }

echo
echo "=============================================================="
echo "  GUIALITA — lokale Einrichtung"
echo "=============================================================="
echo "  Repository: $REPO"
echo

# Suchorte: Repo, Elternverzeichnisse, typische Ablagen, plus --hint
SEARCH_DIRS=("$REPO" "$REPO/.." "$REPO/../.." "$HOME")
for m in /media/*/* /mnt/* /media/*; do
    [ -d "$m" ] && SEARCH_DIRS+=("$m")
done
SEARCH_DIRS+=("${HINTS[@]:-}")

# Sucht eine Datei nach Muster, begrenzte Tiefe, erste Fundstelle gewinnt.
find_file() {
    local pattern="$1" depth="${2:-6}" d hit
    for d in "${SEARCH_DIRS[@]}"; do
        [ -n "$d" ] && [ -d "$d" ] || continue
        hit=$(find "$d" -maxdepth "$depth" -name "$pattern" -type f -print -quit 2>/dev/null)
        [ -n "$hit" ] && { echo "$hit"; return 0; }
    done
    return 1
}

# ---------- 1. whisper.cpp (STT) ----------
echo "  Suche whisper.cpp (STT) …"
WHISPER_CLI=""
if command -v whisper-cli > /dev/null 2>&1; then
    WHISPER_CLI="$(command -v whisper-cli)"
    ok "whisper-cli in \$PATH: $WHISPER_CLI"
else
    for c in "$HOME/whisper.cpp/build/bin/whisper-cli" \
             "$HOME/whisper.cpp/main" \
             "/opt/whisper.cpp/build/bin/whisper-cli"; do
        [ -x "$c" ] && { WHISPER_CLI="$c"; break; }
    done
    if [ -z "$WHISPER_CLI" ]; then
        found=$(find_file "whisper-cli" 6) && WHISPER_CLI="$found"
    fi
    [ -n "$WHISPER_CLI" ] && ok "gefunden: $WHISPER_CLI" \
                          || miss "whisper-cli nicht gefunden — STT bleibt offline"
fi

# ---------- 2. Whisper-Modell ----------
echo "  Suche Whisper-Modell (ggml-*.bin) …"
WHISPER_MODEL=""
found=$(find_file "ggml-base*.bin" 6) && WHISPER_MODEL="$found"
[ -z "$WHISPER_MODEL" ] && { found=$(find_file "ggml-*.bin" 6) && WHISPER_MODEL="$found"; }
[ -n "$WHISPER_MODEL" ] && ok "gefunden: $WHISPER_MODEL" \
                        || miss "kein Whisper-Modell gefunden"

# ---------- 3. Externer Modellspeicher (Granite / LFM-Agent) ----------
echo "  Suche Granite-Modelle …"
EXTERNAL_ROOT=""
granite=$(find_file "granite-4.1-3b*.gguf" 8)
if [ -n "${granite:-}" ]; then
    # …/models/granite/3b/datei.gguf  →  …/models
    EXTERNAL_ROOT="$(dirname "$(dirname "$(dirname "$granite")")")"
    ok "Granite gefunden: $granite"
    info "  → GUIALITA_EXTERNAL_MODEL_ROOT=$EXTERNAL_ROOT"
else
    miss "kein Granite-Modell gefunden — Textchat bleibt offline"
fi

# ---------- 4. Modelle im Repo (LFM Audio / Vision) ----------
echo "  Suche LFM-Audio-Modell …"
MODEL_ROOT=""
audio=$(find_file "LFM2.5-Audio-1.5B-Q4_0.gguf" 8)
if [ -n "${audio:-}" ]; then
    MODEL_ROOT="$(dirname "$(dirname "$audio")")"
    ok "LFM-Audio gefunden: $audio"
    info "  → GUIALITA_MODEL_ROOT=$MODEL_ROOT"
else
    miss "kein LFM-Audio-Modell gefunden — TTS bleibt offline"
fi

# ---------- 5. Liquid-Audio-Runtime ----------
echo "  Suche llama-liquid-audio-cli (TTS-Runtime) …"
RUNTIME_ROOT=""
liquid=$(find_file "llama-liquid-audio-cli" 8)
if [ -n "${liquid:-}" ]; then
    RUNTIME_ROOT="$(dirname "$(dirname "$liquid")")"
    ok "Runtime gefunden: $liquid"
    info "  → GUIALITA_RUNTIME_ROOT=$RUNTIME_ROOT"
else
    miss "llama-liquid-audio-cli nicht gefunden — TTS bleibt offline"
fi

# ---------- 6. Python-Umgebung ----------
echo "  Suche Python-Umgebung …"
VENV=""
for c in "$REPO/.venv" "$HOME/.guialita-venv"; do
    [ -x "$c/bin/python" ] && { VENV="$c"; break; }
done
[ -n "$VENV" ] && ok "Venv: $VENV" || miss "kein Venv — anlegen: python3 -m venv .venv"

# ---------- .env schreiben ----------
echo
echo "--------------------------------------------------------------"
if [ "$DRY_RUN" -eq 1 ]; then
    echo "  --dry-run: es wird nichts geschrieben."
    echo "--------------------------------------------------------------"
    echo
    exit 0
fi

if [ -f "$ENV_FILE" ]; then
    printf "  .env existiert bereits. Überschreiben? [j/N] "
    read -r answer < /dev/tty || answer="n"
    case "$answer" in
        j|J|y|Y) cp "$ENV_FILE" "$ENV_FILE.bak"; info "Sicherung: .env.bak" ;;
        *) echo "  Abgebrochen — .env bleibt unverändert."; echo; exit 0 ;;
    esac
fi

{
    echo "# GUIALITA — lokale Pfadkonfiguration"
    echo "# Erzeugt von scripts/setup_local.sh am $(date '+%Y-%m-%d %H:%M')"
    echo "# Diese Datei ist nicht versioniert und maschinenspezifisch."
    echo
    [ -n "$EXTERNAL_ROOT" ] && echo "GUIALITA_EXTERNAL_MODEL_ROOT=$EXTERNAL_ROOT" \
                            || echo "# GUIALITA_EXTERNAL_MODEL_ROOT=   # nicht gefunden"
    [ -n "$MODEL_ROOT" ]    && echo "GUIALITA_MODEL_ROOT=$MODEL_ROOT" \
                            || echo "# GUIALITA_MODEL_ROOT=            # nicht gefunden"
    [ -n "$RUNTIME_ROOT" ]  && echo "GUIALITA_RUNTIME_ROOT=$RUNTIME_ROOT" \
                            || echo "# GUIALITA_RUNTIME_ROOT=          # nicht gefunden"
    [ -n "$WHISPER_CLI" ]   && echo "GUIALITA_WHISPER_CLI=$WHISPER_CLI" \
                            || echo "# GUIALITA_WHISPER_CLI=           # nicht gefunden"
    [ -n "$VENV" ]          && echo "GUIALITA_VENV=$VENV" \
                            || echo "# GUIALITA_VENV=                  # nicht gefunden"
    echo
    echo "# Datenablage (SQLite). Standard: \$GUIALITA_ROOT/data"
    echo "# GUIALITA_DATA_ROOT="
} > "$ENV_FILE"

ok ".env geschrieben: $ENV_FILE"

if [ -n "$WHISPER_MODEL" ] && [ -n "$MODEL_ROOT" ]; then
    expected="$MODEL_ROOT/whisper/$(basename "$WHISPER_MODEL")"
    if [ ! -f "$expected" ]; then
        echo
        info "Hinweis: Das Whisper-Modell liegt unter"
        info "  $WHISPER_MODEL"
        info "erwartet wird es unter"
        info "  $expected"
        info "Verlinken oder kopieren:"
        info "  mkdir -p \"$MODEL_ROOT/whisper\" && cp \"$WHISPER_MODEL\" \"$expected\""
    fi
fi

echo
echo "  Nächste Schritte:"
echo "    1. Prüfen:  cat .env"
echo "    2. Starten: bash scripts/start.sh"
echo "    3. Testen:  python3 scripts/run_all_tests.py"
echo "--------------------------------------------------------------"
echo
