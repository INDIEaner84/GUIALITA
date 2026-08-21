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
        # Pfad normalisieren (entfernt ../ und Symlink-Umwege)
        [ -n "$hit" ] && { readlink -f "$hit" 2>/dev/null || echo "$hit"; return 0; }
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

# ---------- 4. Modelle in die erwartete Struktur verlinken ----------
# GUIALITA erwartet:  <MODEL_ROOT>/lfm-audio-1.5b/…  und  <MODEL_ROOT>/whisper/…
# Auf echten Maschinen liegen die Dateien oft anders (z. B. models/lfm/audio/).
# Statt die Wurzel zu raten — was bei abweichenden Ordnernamen nicht funktionieren
# kann — werden Symlinks in <REPO>/models/ angelegt. Nichts wird kopiert.
echo "  Suche LFM-Audio-Modell …"
MODEL_ROOT=""
LINK_DIR="$REPO/models"
SYMLINKS_OK=1

link_into_models() {   # $1 = Zielpfad, $2 = Name unter models/
    local target="$1" name="$2" dest="$LINK_DIR/$2"
    mkdir -p "$(dirname "$dest")" 2>/dev/null || { SYMLINKS_OK=0; return 1; }
    [ -e "$dest" ] && [ ! -L "$dest" ] && return 0      # echtes Verzeichnis: nicht anfassen
    rm -f "$dest" 2>/dev/null
    if ln -s "$target" "$dest" 2>/dev/null; then
        ok "models/$name → $target"
        return 0
    fi
    SYMLINKS_OK=0
    return 1
}

audio=$(find_file "LFM2.5-Audio-1.5B-Q4_0.gguf" 8)
if [ -n "${audio:-}" ]; then
    AUDIO_DIR="$(dirname "$audio")"
    ok "LFM-Audio gefunden: $audio"
    if [ "$DRY_RUN" -eq 0 ]; then
        link_into_models "$AUDIO_DIR" "lfm-audio-1.5b"
    else
        info "  → würde verlinken: models/lfm-audio-1.5b → $AUDIO_DIR"
    fi
    for extra in mmproj tokenizer vocoder; do
        [ -f "$AUDIO_DIR/$extra-LFM2.5-Audio-1.5B-Q4_0.gguf" ] \
            || miss "  $extra-Datei fehlt in $AUDIO_DIR — TTS bleibt unvollständig"
    done
else
    miss "kein LFM-Audio-Modell gefunden — TTS bleibt offline"
fi

if [ -n "${WHISPER_MODEL:-}" ]; then
    if [ "$DRY_RUN" -eq 0 ]; then
        link_into_models "$WHISPER_MODEL" "whisper/$(basename "$WHISPER_MODEL")"
    else
        info "  → würde verlinken: models/whisper/$(basename "$WHISPER_MODEL")"
    fi
fi

echo "  Suche LFM-Vision-Modell …"
vision=$(find_file "LFM2.5-VL-3B-Q4_K_M.gguf" 8)
if [ -n "${vision:-}" ]; then
    ok "LFM-Vision gefunden: $vision"
    [ "$DRY_RUN" -eq 0 ] && link_into_models "$(dirname "$vision")" "lfm-vision-3b"
else
    miss "kein LFM-Vision-Modell gefunden (wird derzeit nicht verwendet)"
fi

if [ "$SYMLINKS_OK" -eq 0 ]; then
    miss "Symlinks nicht möglich (exFAT/FAT?) — trage GUIALITA_MODEL_ROOT von Hand ein"
fi

# ---------- 5. Liquid-Audio-Runtime ----------
echo "  Suche llama-liquid-audio-cli (TTS-Runtime) …"
RUNTIME_ROOT=""
liquid=$(find_file "llama-liquid-audio-cli" 8)
if [ -n "${liquid:-}" ]; then
    RUNTIME_ROOT="$(dirname "$(dirname "$liquid")")"
    ok "Runtime gefunden: $liquid"
    info "  → GUIALITA_RUNTIME_ROOT=$RUNTIME_ROOT"
    [ -x "$liquid" ] || miss "  nicht ausführbar — beheben: chmod +x \"$liquid\""
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
    if [ "$SYMLINKS_OK" -eq 1 ]; then
        echo "# GUIALITA_MODEL_ROOT=            # Standard: \$GUIALITA_ROOT/models (Symlinks angelegt)"
    else
        echo "# GUIALITA_MODEL_ROOT=            # Symlinks fehlgeschlagen - bitte von Hand setzen"
    fi
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

echo
echo "  Nächste Schritte:"
echo "    1. Prüfen:  cat .env"
echo "    2. Starten: bash scripts/start.sh"
echo "    3. Testen:  python3 scripts/run_all_tests.py"
echo "--------------------------------------------------------------"
echo
