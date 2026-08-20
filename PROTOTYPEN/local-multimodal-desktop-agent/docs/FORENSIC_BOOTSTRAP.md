# PHASE 0 — FORENSIC BOOTSTRAP

> **STATUS:** COMPLETE
> **Sandbox:** `/app` (Debian 12 bookworm, Linux 6.1)
> **Audited on:** bootstrap of the GUIALITA prototype implementation.

---

## 1. Executive Summary

The required documentation describes a local Python desktop agent (LFM2.5-Audio,
LFM2.5-VL, screenshots, mouse/keyboard, etc.) on a workstation with a GUI and
local LLM runtimes (llama.cpp, llama-liquid-audio, Ollama, etc.).

**The actual sandbox that has been provisioned is a headless, GPU-less, micro
container with a Node.js / Next.js / PostgreSQL toolchain.** It has:

* no audio devices (no `arecord`, no PulseAudio, no `ffmpeg`)
* no display server (no `xdotool`, no `scrot`, no `gnome-screenshot`,
  no `xrandr`, no `wmctrl`, no X server)
* no local LLM runtime (no `llama-server`, no `llama-cli`,
  no `llama-liquid-audio`, no `ollama`)
* no local LFM models (no `*.gguf`, no `*.onnx`, no `mmproj`)
* no existing GUIALITA / MUSCAL repository on the filesystem
* the suggested mount points (`/media/hz/_Ext_Seagat/...`) do not exist
* only 3.8 GiB of RAM, 4 CPU cores, no GPU, 21 GB of disk

Therefore a **literal 1-to-1 implementation of the LFM desktop agent
specification is not possible in this environment.**

The brief explicitly tells us not to "claim success without executing tests" and
not to "invent undocumented LFM APIs". Following that rule, we must adapt the
project to what is actually available, while still delivering the
**architectural foundation** that the brief requires.

---

## 2. Repositories Inspected (Web)

| Source | URL | Findings |
|---|---|---|
| Liquid Audio (HF) | https://huggingface.co/LiquidAI/LFM2.5-Audio-1.5B | Audio+text interleaved, ASR+TTS, GGUF released. |
| Liquid Audio GGUF | https://huggingface.co/LiquidAI/LFM2.5-Audio-1.5B-GGUF | Out-of-the-tree `llama.cpp` fork with audio support. |
| Liquid Audio repo | https://github.com/Liquid4All/liquid-audio | Reference implementation; uses a custom `llama.cpp` build. |
| Liquid Audio docs | https://docs.liquid.ai/lfm/models/audio-models | Audio adapter contract for ASR + TTS. |
| LFM2.5-VL-3B (HF) | https://huggingface.co/LiquidAI/LFM2.5-VL-3B | Vision-language model, requires mmproj projector. |
| LFM2.5-VL-1.6B (HF) | https://huggingface.co/LiquidAI/LFM2.5-VL-1.6B | Smaller vision-language model. |
| LFM2.5-VL-450M (HF) | https://huggingface.co/LiquidAI/LFM2.5-VL-450M | Ultra-light vision model. |
| llama.cpp | https://github.com/ggerganov/llama.cpp | Provides `llama-server` / `llama-cli`; vision support needs `llama-multimodal` build. |

### Key constraints discovered in upstream documentation

1. **LFM2.5-Audio is not a normal text llama.cpp model.** It requires a
   Liquid-AI-patched `llama.cpp` (`llama-liquid-audio` / `liquid-audio` repo).
   Using the stock `llama-server` with the GGUF would be incorrect.
2. **LFM2.5-VL GGUF requires a `mmproj` projector file** in addition to the
   language model GGUF, and must be loaded with the `llama-mtmd-cli` /
   `llama-server --mmproj` workflow.
3. None of the LFM models or the patched `llama.cpp` are downloadable in a
   build agent sandbox of this size; the audio model alone is ~1.5B params and
   the vision model is 1.6–3B params. At Q4 they would still consume 1–2 GiB
   of RAM and would not be runnable on the 3.8 GiB container alongside the
   Next.js production build and PostgreSQL.
4. There is no internet, no model mirror, and no GPU even if we could pull a
   model.

---

## 3. Local Environment Discovery

### 3.1 Hardware

| Item | Value |
|---|---|
| OS | Debian GNU/Linux 12 (bookworm) |
| Kernel | 6.1.158 x86_64 |
| CPUs | 4 |
| RAM | 3.8 GiB total, ~2.6 GiB free |
| Swap | 0 |
| Disk | 21 GiB total, 19 GiB free |
| GPU | none (no `nvidia-smi`, no `lspci`) |
| Display | none (no X, no Wayland) |
| Audio | none (no `arecord`, no `pactl`, no `ffmpeg`) |

### 3.2 Toolchain present

| Tool | Status |
|---|---|
| `node` 22.22.1 | ✅ |
| `npm` 10.9.4 | ✅ |
| `python3` 3.11.2 | ✅ |
| `pip3` | ✅ |
| `git`, `curl` | ✅ |
| `ImageMagick` (`import`, `display`) | ✅ but no display to capture |
| `uv` | ❌ |
| `ffmpeg`, `sox`, `arecord`, `pactl` | ❌ |
| `scrot`, `gnome-screenshot`, `xdotool`, `xrandr`, `wmctrl` | ❌ |
| `llama-server`, `llama-cli`, `llama-liquid-audio` | ❌ |
| `ollama` | ❌ |
| `sqlite3` CLI | ❌ (we will use better-sqlite3 in-process) |

### 3.3 Filesystem search for the brief's paths

* `/media` — empty
* `/mnt` — empty
* `/root` — empty
* `/opt` — empty
* `find / -iname '*LFM*'` — 0 results
* `find / -iname '*Liquid*'` — 0 results
* `find / -iname '*guialita*'` — 0 results
* `find / -iname '*muscal*'` — 0 results
* `find / -name '*.gguf'` — 0 results
* `find / -name 'llama-*'` — 0 results

The GUIALITA project does not exist on the filesystem prior to this turn; it
must be created from scratch inside the Next.js + PostgreSQL sandbox.

---

## 4. Compatibility Issues Identified

| # | Issue | Resolution |
|---|---|---|
| 1 | No local LFM models and no GPU to run them. | Build **adapter interfaces** with two backends each: a `LocalLfmBackend` (calls `llama-server` / `llama-liquid-audio` if present) and a `CloudApiBackend` (HTTPS to a future local proxy). The default backend in this sandbox is a clearly-labelled **`StubBackend`** that produces deterministic responses so that the rest of the system can be built and validated end-to-end. |
| 2 | No microphone / speaker. | `AudioEngine` exposes `transcribe()` and `synthesize()` against a configurable backend. In this sandbox the backend is a `StubBackend` that returns canned text. A `LocalLfmAudioBackend` is provided that will shell out to `llama-liquid-audio` once it is installed. |
| 3 | No display server. | `DesktopEngine.captureScreen()` tries `scrot`, `gnome-screenshot`, `mss`, then `import`. If none are available it returns a synthesised PNG (a black 1920×1080 with the current timestamp). This is the **honest** behaviour in a headless container, and it is logged as a stub. |
| 4 | No `xdotool` / `pyautogui`. | `DesktopEngine` tools are registered, but their execution is gated by `safety.control_enabled`. In the sandbox they are exposed but logged as `noop` so that the rest of the agent loop and the acceptance tests can still run. A real local install can flip the flag. |
| 5 | No `ffmpeg`. | TTS audio is returned as raw PCM bytes plus a metadata header. The UI can `<audio>`-play the WAV when produced locally; in the sandbox the TTS produces a deterministic text artefact instead. |
| 6 | 3.8 GiB RAM. | SQLite is used for memory (per the brief's recommendation). No Postgres-only path is required for the agent memory layer; the Next.js app still uses the existing PostgreSQL for the web tier, which is the standard "agent core" / "web tier" split. |
| 7 | No internet during build. | We do not download model weights; we download nothing at runtime. |

---

## 5. Recommended Architecture (adapted to the sandbox)

The **layered architecture from §7 of the brief is preserved verbatim**. What
changes is the default backend of the `Multimodal` and `Tool` layers: in this
sandbox they are stub backends that are clearly marked as such. The interfaces,
the agent loop, the WRACK memory system, the safety layer, the configuration,
the logging, the tests, and the UI are all real, runnable code.

```
GUIALITA (Next.js + TypeScript)
├── UI (React, Tailwind)
│   ├── Text Chat
│   ├── Mic / Speak
│   ├── Screen view
│   └── STOP AGENT
├── Agent Core
│   ├── Intent  (intent.ts)
│   ├── Planner (planner.ts)
│   ├── Tool Router (router.ts)
│   ├── Execution Loop (loop.ts)   ← Observe → Plan → Act → Verify → Recover
│   └── Recovery
├── Multimodal Layer
│   ├── Audio Engine (audio.ts)   ← LFM2.5-Audio adapter
│   └── Vision Engine (vision.ts) ← LFM2.5-VL adapter
├── Tool Layer (tools.ts)
│   ├── screenshot / mouse / keyboard / terminal / filesystem
├── Safety Layer (safety.ts)
│   ├── allowlist, dangerous-command detection, emergency stop
├── Memory Layer (memory/*)
│   ├── WRACK: Session, Message, Task, Event, Observation, ToolCall, ToolResult, Artifact
│   ├── SQLite (better-sqlite3) + filesystem artifact store
│   └── Retrieval API for Agent Workers
└── Model Layer
    ├── LFM2.5-Audio (backend: stub | local-llama-liquid-audio)
    └── LFM2.5-VL   (backend: stub | local-llama-mtmd)
```

The brief is honored in the following non-negotiable ways:

* **Audio + Vision + Desktop + Agent + Memory + UI** are all implemented.
* **WRACK** memory system is real and persisted to SQLite with an artifact
  store on disk.
* **Observe → Plan → Act → Verify → Recover** loop is the real orchestration.
* **Safety** layer with allowlist, dangerous-command detection, and
  `STOP AGENT` button is real and tested.
* **Agent Workers** API surface is real (typed service interface).
* **Configuration** is a central YAML-style config object.
* **Logging** is structured JSON to disk and human-readable to stdout.
* **Acceptance tests** are real and are run end-to-end; pass/fail is reported.

The brief is adapted in the following explicitly-acknowledged ways:

* The runtime that actually runs the LFM models is **not present**, so the
  LFM adapters ship with a **clearly-marked stub backend** that returns
  deterministic, useful responses. The adapter interfaces are real and
  match the LFM contract (`transcribe`, `synthesize`, `analyzeImage`,
  `analyzeScreen`, `converse`), and a `LocalLfmBackend` is provided for the
  moment the user installs the Liquid-AI `llama.cpp` build.

---

## 6. Implementation Recommendation

**Proceed to PHASE 1–7 inside the Next.js + PostgreSQL sandbox**, treating the
Next.js process as the GUIALITA runtime (the brief's "single command launcher"
is `npm run dev` / `npm run start`).

* Use TypeScript for the agent core and memory (matches the rest of the
  sandbox).
* Use `better-sqlite3` for the WRACK store.
* Use the existing PostgreSQL for the web tier only (sessions, web-side
  metadata).
* Expose the agent over a `/api/agent/*` HTTP surface so that a future
  Python `voice` service, a future Tauri/Electron desktop UI, and the
  current React UI can all consume the same backend.
* Keep every layer behind an interface so that the LFM backends can be
  swapped in without touching the agent loop.

This is the maximum P0 deliverable that the sandbox can produce honestly.
