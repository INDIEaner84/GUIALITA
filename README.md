# GUIALITA — Lokaler LFM-Sprachassistent

**Browser → Local LFM → Memory → Sprache**

> Aktueller Stand: Voice Activation V1, persistente Sessions, Memory-Retrieval,
> Knowledge-Graph, Whisper-STT und LFM-TTS sind implementiert. Die kanonische
> Pipeline ist lokal und hardwareabhängig; Vision/Desktop-Control liegen noch
> als separate Prototypen unter `PROTOTYPEN/` vor.

## Schnellstart

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/doctor.py
GUIALITA_VENV="$PWD/.venv" bash scripts/start.sh
```

Die Modellpfade in `config/models.yaml` müssen zur lokalen Installation passen.
Absolute Pfade können durch Umgebungsvariablen ersetzt werden, zum Beispiel:

```yaml
path: ${GUIALITA_MODEL_ROOT}/granite/3b/model.gguf
```

Dann vor dem Start setzen:

```bash
export GUIALITA_MODEL_ROOT=/pfad/zu/models
export GUIALITA_WHISPER_CLI=/pfad/zu/whisper-cli
```

`doctor.py` ist schreibgeschützt und verändert weder Ollama noch Modelle.

**Browser → Local LFM → Browser**

Phase 0 ist ein technischer Proof of Function: Ein lokal laufendes LFM-Modell
wird über einen lokalen Backend-Service aus dem Browser angesprochen.

```
BROWSER
   ↓
LOCAL API (FastAPI, Port 8080)
   ↓
MODEL ADAPTER (llama-cpp-python primär, Ollama sekundär)
   ↓
LFM RUNTIME (GPU: GTX 1080 Ti / CPU-Fallback)
   ↓
LOCAL API
   ↓
BROWSER
```

---

## Verwendete Komponenten

| Komponente | Wert |
|------------|------|
| **Primärmodell** | Granite 4.1 3B (`granite-4.1-3b-Q4_K_M.gguf`, 2.1 GB) |
| **Primäre Runtime** | llama-cpp-python 0.3.35 (mit CUDA) |
| **Sekundäre Runtime** | Ollama (SHARED SERVICE, Port 11434) |
| **Backend** | FastAPI + Uvicorn, Port 8080 |
| **Frontend** | Reines HTML/JS (kein Framework) |
| **GPU** | NVIDIA GTX 1080 Ti (11 GB VRAM, CUDA 12.0) |

### Weitere Modelle (für spätere Phasen)

| Modell | Pfad | Phase |
|--------|------|-------|
| LFM2.5-VL-3B (Vision) | `models/lfm-vision-3b/` | Phase 2 |
| LFM2.5-VL-1.6B (Vision) | `models/lfm-vision-1.6b/` | Phase 2 |
| LFM2.5-Audio-1.5B (Audio) | `models/lfm-audio-1.5b/` | Phase 1 |
| Granite 4.1 8B | `…/models/granite/8b/` (extern) | später |
| LFM2.5-8B-A1B (Agent) | `…/models/lfm/agent/` (extern) | später |

> Hinweis: Die Granite-/LFM-Modelle liegen auf `/media/hz/_Ext_Seagat/AiEnvHz/LFM Granite Muscal/models/`
> und werden per Pfad-Referenz genutzt. Die Platte ist exFAT und unterstützt
> keine Symlinks - die Config referenziert die Originalpfade direkt.

---

## Voraussetzungen

- Linux (getestet: Ubuntu 24.04, XFCE)
- Python 3.10+ mit venv
- NVIDIA GPU mit CUDA-Toolkit (optional, CPU-Fallback vorhanden)
- ~6 GB freier Speicher (Modelle)

---

## Installation

```bash
# 1. Python-Venv erstellen (einmalig)
python3 -m venv /home/hz/.guialita-venv

# 2. Abhängigkeiten installieren (einmalig, ~15 Min mit CUDA-Build)
export CMAKE_ARGS="-DGGML_CUDA=on"
export CUDA_HOME=/usr
/home/hz/.guialita-venv/bin/pip install llama-cpp-python fastapi uvicorn pydantic pyyaml httpx

# 3. Desktop-Starter installieren (einmalig)
bash /media/hz/_Ext_Seagat/GUIALITA/scripts/install_desktop.sh
```

## Start

### Über das Anwendungsmenü (empfohlen)

1. Anwendungsmenü öffnen
2. **GUIALITA** wählen (Kategorie: Entwicklung)
3. Backend startet automatisch
4. Browser öffnet sich: `http://localhost:8080`

### Manuell über Terminal

```bash
bash /media/hz/_Ext_Seagat/GUIALITA/scripts/start.sh
```

### Stoppen

```bash
bash /media/hz/_Ext_Seagat/GUIALITA/scripts/stop.sh
```

> **Wichtig:** `stop.sh` beendet NUR GUIALITA-Prozesse. Ollama ist ein
> SHARED SERVICE und wird niemals beendet oder verändert.

---

## Start-Ablauf (start.sh)

1. Umgebung prüfen (venv, Port 8080)
2. Backend starten (PID-Datei in `scripts/logs/guialita.pid`)
3. Auf `/health` warten (max. 60 s)
4. Verfügbarkeit des Primärmodells prüfen
5. Ollama nur ERKENNEN (nicht beenden, nicht konfigurieren)
6. Browser öffnen: `http://localhost:8080`

## API-Endpunkte

### `GET /health`

```json
{
  "api": "online",
  "default_model": "granite-3b",
  "primary_runtime": { "runtime": "llama-cpp-python", "status": "online", "gpu": true },
  "secondary_runtime": { "status": "online", "runtime": "ollama", "models": ["…"] },
  "models": [ { "id": "granite-3b", "name": "granite-4.1-3b", "available": true, … } ],
  "latency_ms": 3.2
}
```

### `GET /models`

Listet alle konfigurierten Modelle mit Verfügbarkeit.

### `POST /chat`

```json
// Request
{ "message": "Hallo", "model": "granite-3b" }

// Success
{ "status": "success", "response": "…", "model": "granite-4.1-3b", "latency_ms": 283, "runtime": "llamacpp" }

// Error
{ "status": "error", "error": "…", "model": "…", "runtime": "…", "details": "…" }
```

---

## Tests

Voraussetzung: Backend läuft.

```bash
cd /media/hz/_Ext_Seagat/GUIALITA
/home/hz/.guialita-venv/bin/python tests/test_api.py
```

Enthaltene Tests:

1. **API Health Test** - `/health` liefert API- und Runtime-Status
2. **Model Connectivity Test** - Modelle gelistet und verfügbar
3. **Chat API Test** - Erfolg, Fehlerfälle, Format
4. **End-to-End Test** - echter Chat: "…CONNECTION TEST OK" muss vom LFM kommen

---

## Fehlerdiagnose

| Symptom | Ursache | Aktion |
|---------|---------|--------|
| Browser zeigt OFFLINE | Backend läuft nicht | `start.sh` ausführen, Log prüfen |
| Modell "fehlt" in GUI | GGUF-Datei nicht gefunden | Pfade in `config/models.yaml` prüfen |
| "Ollama nicht erreichbar" | Ollama gestoppt (SHARED) | `ollama serve` separat starten |
| CUDA-Fehler beim Laden | GPU-Load fehlgeschlagen | Adapter fällt automatisch auf CPU zurück |
| Backend startet nicht | Port 8080 belegt | Log: `scripts/logs/backend.log` prüfen |
| Langsame erste Antwort | Erstes Laden des Modells | Normal (30-60 s), danach schnell (GPU) |

### Logs

```bash
tail -f /media/hz/_Ext_Seagat/GUIALITA/scripts/logs/backend.log
```

---

## Projektstruktur

```
GUIALITA/
├── README.md
├── config/models.yaml        # Modell- und Server-Konfiguration
├── backend/
│   ├── main.py               # FastAPI-Server (Port 8080)
│   ├── manager.py            # Modell-Manager (Adapter-Auswahl)
│   ├── adapters/
│   │   ├── base.py           # Abstracte Adapter-Schnittstelle
│   │   ├── llamacpp_adapter.py  # PRIMÄR: llama-cpp-python (dediziert)
│   │   └── ollama_adapter.py    # SEKUNDÄR: Ollama (shared, wird nie beendet)
│   ├── models/schemas.py     # Pydantic-Schemas
│   └── utils/latency.py      # Latenz-Messung
├── frontend/index.html       # Minimaler Chat-UI
├── models/                   # Heruntergeladene LFM-Modelle
│   ├── lfm-audio-1.5b/
│   ├── lfm-vision-3b/
│   └── lfm-vision-1.6b/
├── scripts/
│   ├── start.sh              # Hauptstart (Menü + Terminal)
│   ├── stop.sh               # Stoppt nur GUIALITA-Prozesse
│   ├── download_models.sh    # LFM-Modelle von Hugging Face
│   └── install_desktop.sh    # Installiert GUIALITA.desktop
└── tests/test_api.py         # Health-, Chat-, E2E-Tests
```

---

## Phasenplan

| Phase | Inhalt | Status |
|-------|--------|--------|
| **0** | Browser → Local LFM → Browser | ✅ abgeschlossen |
| 1 | Microphone → LFM Audio → Text → Browser | Modell vorhanden |
| 2 | LFM Vision → Desktop erkennen | Modell vorhanden |
| 3 | Desktop Control / Computer Use | – |
| 4 | Knowledge Objects | – |
| 5 | Worker-Agenten | – |
| 6+ | Overlay, Graph, Multi-Device | – |