#!/bin/bash
# GUIALITA - Modell-Downloader
# Laedt die LFM Audio/Vision Modelle von Hugging Face herunter.
# Die Granite-Modelle sind bereits auf der Platte vorhanden.

set -u

GUIALITA_DIR="/media/hz/_Ext_Seagat/GUIALITA"
MODELS_DIR="$GUIALITA_DIR/models"

info() { echo "[GUIALITA] $*"; }

mkdir -p "$MODELS_DIR/lfm-vision-3b" "$MODELS_DIR/lfm-vision-1.6b" "$MODELS_DIR/lfm-audio-1.5b"

info "=== GUIALITA Modell-Download ==="
info "Ziel: $MODELS_DIR"

download() { # $1=repo  $2=dir  $3=file
    local url="https://huggingface.co/$1/resolve/main/$3"
    if [ -s "$MODELS_DIR/$2/$3" ]; then
        info "OK (vorhanden): $2/$3"
        return 0
    fi
    info "Downloade: $2/$3"
    wget -c -q --show-progress "$url" -O "$MODELS_DIR/$2/$3"
    if [ $? -ne 0 ]; then
        error() { echo "[GUIALITA][FEHLER] $*"; }
        error "Download fehlgeschlagen: $url"
        return 1
    fi
}

download "LiquidAI/LFM2.5-VL-3B-GGUF"     "lfm-vision-3b"   "LFM2.5-VL-3B-Q4_K_M.gguf"
download "LiquidAI/LFM2.5-VL-3B-GGUF"     "lfm-vision-3b"   "mmproj-LFM2.5-VL-3B-Q8_0.gguf"
download "LiquidAI/LFM2.5-VL-1.6B-GGUF"   "lfm-vision-1.6b" "LFM2.5-VL-1.6B-Q4_K_M.gguf"
download "LiquidAI/LFM2.5-VL-1.6B-GGUF"   "lfm-vision-1.6b" "mmproj-LFM2.5-VL-1.6b-Q8_0.gguf"
download "LiquidAI/LFM2.5-Audio-1.5B-GGUF" "lfm-audio-1.5b" "LFM2.5-Audio-1.5B-Q4_0.gguf"
download "LiquidAI/LFM2.5-Audio-1.5B-GGUF" "lfm-audio-1.5b" "mmproj-LFM2.5-Audio-1.5B-Q4_0.gguf"
download "LiquidAI/LFM2.5-Audio-1.5B-GGUF" "lfm-audio-1.5b" "tokenizer-LFM2.5-Audio-1.5B-Q4_0.gguf"
download "LiquidAI/LFM2.5-Audio-1.5B-GGUF" "lfm-audio-1.5b" "vocoder-LFM2.5-Audio-1.5B-Q4_0.gguf"

info "=== Download abgeschlossen ==="
ls -lh "$MODELS_DIR/lfm-vision-3b" "$MODELS_DIR/lfm-vision-1.6b" "$MODELS_DIR/lfm-audio-1.5b" 2>/dev/null
exit 0
