# GUIALITA Phase 0 Baseline

## Status

PASS

## Date

2026-08-18

## Hardware

| Komponente | Wert |
|------------|------|
| Host | ThinkPadT (Linux Mint 22.3) |
| Kernel | 6.14.0-37-generic (x86_64) |
| CPU | Intel Core i7-3930K, 6C/12T, 3.2 GHz |
| RAM | 31 GiB (ca. 13 GiB verfügbar) |
| GPU | NVIDIA GeForce GTX 1080 Ti, 11264 MiB VRAM |
| GPU Driver | 535.288.01 |
| CUDA Driver-Version | 12.2 (Toolkit 12.0, nvcc V12.0.140) |
| Datenträger | `/media/hz/_Ext_Seagat` exFAT (keine Symlinks möglich) |

## Runtime

| Komponente | Version | Status |
|------------|---------|--------|
| Python | 3.12.3 | ✓ |
| pip | 24.0 | ✓ |
| llama-cpp-python | 0.3.35 | ✓ (CUDA-Build, libggml-cuda.so verifiziert) |
| fastapi | 0.141.1 | ✓ |
| uvicorn | 0.52.3 | ✓ |
| pydantic | 2.13.4 | ✓ |
| httpx | 0.28.1 | ✓ |
| PyYAML | 6.0.3 | ✓ |
| numpy | 2.5.2 | ✓ |
| Ollama (SHARED) | 0.30.10 | ✓ Port 11434 |
| venv | `/home/hz/.guialita-venv` | ✓ |

CUDA-Bibliotheken gelinkt: libcublas.so.12, libcublasLt.so.12, libcudart.so.12,
libcuda.so.1, libggml-cuda.so.0

## Models

| Model ID | Runtime | Path | Format | Quantization | Size | Status |
|----------|---------|------|--------|--------------|------|--------|
| granite-3b | llamacpp | `…/LFM Granite Muscal/models/granite/3b/granite-4.1-3b-Q4_K_M.gguf` | GGUF | Q4_K_M | 2.1 GB | **VERIFIED** |
| granite-8b | llamacpp | `…/LFM Granite Muscal/models/granite/8b/granite-4.1-8b-Q4_K_M.gguf` | GGUF | Q4_K_M | 5.35 GB | AVAILABLE |
| lfm-agent-8b | llamacpp | `…/LFM Granite Muscal/models/lfm/agent/LFM2.5-8B-A1B-Q4_K_M.gguf` | GGUF | Q4_K_M | 5.16 GB | AVAILABLE |
| lfm-vision-3b | llamacpp | `models/lfm-vision-3b/LFM2.5-VL-3B-Q4_K_M.gguf` + mmproj | GGUF | Q4_K_M | 1.67 GB | AVAILABLE |
| lfm-vision-1.6b | llamacpp | `models/lfm-vision-1.6b/LFM2.5-VL-1.6B-Q4_K_M.gguf` + mmproj | GGUF | Q4_K_M | 0.73 GB | **TESTED** |
| lfm-audio-1.5b | llamacpp | `models/lfm-audio-1.5b/LFM2.5-Audio-1.5B-Q4_0.gguf` + mmproj + tokenizer + vocoder | GGUF | Q4_0 | 0.70 GB | **TESTED** |

Alle Modelle: n_ctx=4096, n_gpu_layers=99 (volle GPU-Offload, CPU-Fallback bei
Fehler automatisch).

Status-Definition:
- **AVAILABLE** = Datei vorhanden und über API gelistet
- **LOADED** = konnte geladen werden
- **TESTED** = Chat-Inferenz erfolgreich ausgeführt
- **VERIFIED** = End-to-End getestet, exakte Antwort verifiziert

Ollama (SHARED): 17 Modelle verfügbar (qwen2.5:7b-instruct, deepseek-r1:8b,
minicpm-v, qwen3, starcoder2 u.a.)

## Architecture

```
                 GUIALITA
                     |
               Model Adapter
                     |
          +----------+----------+
          |                     |
     llama.cpp              Ollama
      PRIMARY              SECONDARY
      dedicated              shared
```

- **PRIMARY** (dediziert): llama-cpp-python, CUDA, Port frei im Backend
- **SECONDARY** (shared): Ollama auf Port 11434 - wird nur erkannt und
  optional genutzt, niemals beendet oder konfiguriert

Backend: FastAPI + Uvicorn, Port 8080, Host 0.0.0.0
Frontend: statisches HTML/JS unter `/`, Backend unter `/health`, `/models`, `/chat`

## API

| Endpoint | Methode | Erfolg | Fehler |
|----------|---------|--------|--------|
| `/health` | GET | 200, api/models/runtimes/GPU-Status | 000 wenn offline |
| `/models` | GET | 200, Modellliste mit Verfügbarkeit | - |
| `/chat` | POST | 200 `{status, response, model, latency_ms, runtime}` | 400/404/422/500 mit Diagnose |
| `/` | GET | 200, Frontend | - |

## Tests

Ausgeführt am 2026-08-18 gegen laufende Instanz (Port 8080):

| Test | Ergebnis |
|------|----------|
| Health 200 + api:online | PASS |
| Health enthält Runtimes + Modelle | PASS |
| Modelle gelistet, >=1 verfügbar | PASS |
| granite-3b verfügbar | PASS |
| Chat leere Nachricht → 400 | PASS |
| Chat unbekanntes Modell → 404 | PASS |
| Chat Erfolgsformat (status/response/model/latency) | PASS |
| Frontend wird ausgeliefert | PASS |
| E2E: echte LFM-Antwort "…CONNECTION TEST OK" | PASS |

**9/9 Tests bestanden.**

## Latency

| Messung | Wert | Bemerkung |
|---------|------|-----------|
| Cold start (Modell-Load) | ~1176 ms | nach Backend-Neustart, warmer OS-Page-Cache |
| Allererster Start (CUDA-JIT + kalter Cache) | 50–66 s | einmalig, dokumentiert |
| Warm inference (Granite-3B) | 29–48 ms | 3 Messungen, Mittel ~39 ms |
| Warm inference exakter Test | 114 ms | "LFM CONNECTION TEST OK" |
| VL-1.6B First-Load | 66.6 s | danach GPU-schnell |
| Audio-1.5B First-Load | 57.7 s | antwortet auch als Textmodell |

GPU: 5.8 GiB VRAM belegt bei 2 geladenen Modellen, GPU-Util ~15-25% bei Inference.

## Error Handling

| Fall | HTTP | Antwort | Bewertung |
|------|------|---------|-----------|
| Ungültiger Endpoint | 404 | FastAPI-Default | ok |
| Leere Chat-Nachricht | 400 | `{status:error, error:empty_message, details:…}` | gut |
| Unbekanntes Modell | 404 | `{error:unknown_model, details:<Modellliste>}` | gut |
| Kein JSON-Body | 422 | FastAPI-Validierung | ok |
| Modell nicht ladbar | 500 | `{status:error, error, model, runtime, details}` | entworfen, CUDA→CPU-Fallback aktiv |

## Ollama Isolation

| Prüfung | Ergebnis |
|---------|----------|
| Ollama läuft | PASS (PID, Port 11434, HTTP 200) |
| GUIALITA erkennt Ollama | PASS (/health secondary_runtime) |
| GUIALITA kann Ollama nutzen | PASS (Adapter vorhanden, optional) |
| GUIALITA beendet Ollama nicht | PASS (stop.sh killt nur Backend-PID) |
| GUIALITA verändert Ollama nicht | PASS (nur GET /api/tags) |
| Stoppen lässt Ollama laufen | PASS (gleiche PID vor/nach Stop, HTTP 200) |

## Desktop Starter

| Prüfung | Ergebnis |
|---------|----------|
| .desktop-Datei vorhanden | PASS (`~/.local/share/applications/GUIALITA.desktop`) |
| Im Anwendungsmenü | PASS (Kategorie Utility;Development;ArtificialIntelligence) |
| Backend startet | PASS (start.sh, PID-Datei) |
| /health wird verfügbar | PASS (wartet bis 60 s) |
| Browser öffnet sich | PASS (xdg-open http://localhost:8080) |
| Chat funktioniert | PASS |
| Stop beendet nur GUIALITA | PASS |
| Ollama bleibt verfügbar | PASS |

Startmechanismus: `Exec=bash /media/hz/_Ext_Seagat/GUIALITA/scripts/start.sh`

## Startup / Shutdown

- `start.sh`: prüft venv → startet Backend via nohup → PID-Datei
  `scripts/logs/guialita.pid` → wartet auf /health → prüft Primärmodell →
  erkennt Ollama (nur ERKENNEN) → öffnet Browser
- `stop.sh`: beendet PID aus PID-Datei (alternativ pgrep-Filter auf
  `backend/main.py` mit venv-/GUIALITA-Pfad-Prüfung) → prüft Port 8080
- Keine Zombies durch GUIALITA (gefundener `sd_espeak-ng-mb` Zombie ist ein
  fremder Altprozess vom 22.07., nicht von GUIALITA)
- Bekannt: Startet der Benutzer während einer laufenden Instanz erneut über
  den Desktop-Starter, prüft start.sh /health und startet NICHT doppelt.

## Known Limitations

1. exFAT-Dateisystem: keine Symlinks → Modellpfade sind absolute Pfade in
   `config/models.yaml`
2. Erster Modell-Load eines zuvor ungeladenen Modells dauert 50–66 s
   (CUDA-Kernel-Initialisierung + Offload)
3. LFM-Audio-1.5B ist nur als Textmodell getestet (Audio-Input ist Phase 1)
4. LFM-VL-Modelle nur als Textmodell getestet (Bild-Input ist Phase 2)
5. granite-8b / lfm-agent-8b: Datei vorhanden, noch nicht inferenziert
   (spart VRAM, kein Bedarf in Phase 0)
6. 8.5 GB frei auf /media/hz/_Ext_Seagat; ~4.6 GB durch GUIALITA-Modelle
   belegt - Downloads weiterer Modelle benötigen Speicherprüfung
7. Interne Platte / ist zu 98% belegt (venv liegt auf /home/hz)

## Known Risks

1. Zwei GUIALITA-Instanzen können existieren, wenn während laufender Instanz
   der Starter erneut ausgeführt wird und der Health-Check durch einen
   teilfertigen Start übersehen wird (beobachtet: zweiter Backend-Prozess
   nach Stop während laufender Nutzung). PID-Datei verhindert den Normalfall.
2. GPU-Treiber/CUDA-Updates können den CUDA-Build von llama-cpp-python
   invalidieren → erneuter Build nötig (CMAKE_ARGS=-DGGML_CUDA=on)
3. venv auf interner Platte: Wenn / voll läuft, Start nicht möglich
4. Ollama-Modelle auf interner Platte belegen weiter Speicher

## Reproduction Procedure

1. `python3 -m venv /home/hz/.guialita-venv` (einmalig)
2. `export CMAKE_ARGS="-DGGML_CUDA=on" && export CUDA_HOME=/usr` und
   `/home/hz/.guialita-venv/bin/pip install llama-cpp-python fastapi uvicorn pydantic pyyaml httpx` (einmalig)
3. `bash /media/hz/_Ext_Seagat/GUIALITA/scripts/install_desktop.sh` (einmalig)
4. Anwendungsmenü → **GUIALITA** (oder `bash …/scripts/start.sh`)
5. Browser: http://localhost:8080
6. Test: `…/tests/test_api.py` gegen laufendes Backend
7. Stopp: `bash …/scripts/stop.sh`

## Integrity Marker

`GUIALITA-PHASE-0-PASS`

Timestamp: 2026-08-18 19:06 CEST
Environment Fingerprint: Linux Mint 22.3 / i7-3930K / GTX 1080 Ti / llama-cpp-python 0.3.35 CUDA / FastAPI 0.141.1 / Port 8080 / Granite 4.1 3B Q4_K_M
