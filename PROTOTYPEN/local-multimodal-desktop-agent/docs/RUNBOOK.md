# GUIALITA — Runbook

## Quick start

```bash
# 1. Install dependencies
npm install

# 2. Run the acceptance tests (no LFM models required)
bash scripts/run_acceptance_tests.sh

# 3. Launch the agent and the UI
./run_gui_alita.sh
#   → open http://localhost:3000
```

The launcher (`run_gui_alita.sh`) is the single command entry-point
required by §24 of the brief. It verifies dependencies, prepares
the data directory, runs the acceptance tests, then starts the
production server.

## Configuration

All configuration lives in `src/gui_alita/config.ts`. The most
relevant environment overrides are:

| Variable | Default | Purpose |
|---|---|---|
| `GUIALITA_DATA_DIR` | `./data` | Where WRACK, logs, and artifacts live |
| `GUIALITA_AUDIO_PROVIDER` | `stub` | `stub` \| `local-llama-liquid-audio` \| `cloud` |
| `GUIALITA_VISION_PROVIDER` | `stub` | `stub` \| `local-llama-mtmd` \| `cloud` |
| `GUIALITA_AGENT_PROVIDER` | `stub` | `stub` \| `local-llama-text` \| `cloud` |
| `GUIALITA_AUDIO_MODEL_PATH` | — | Path to LFM2.5-Audio GGUF |
| `GUIALITA_VISION_MODEL_PATH` | — | Path to LFM2.5-VL GGUF |
| `GUIALITA_VISION_MMPROJ_PATH` | — | Path to LFM2.5-VL mmproj projector |
| `GUIALITA_AGENT_ENDPOINT` | — | llama-server `/v1/chat/completions` |
| `GUIALITA_AGENT_MAX_STEPS` | `8` | Max Observe→Act cycles per request |
| `GUIALITA_SCREENSHOT_ENABLED` | `true` | Allow screenshot tool |
| `GUIALITA_CONTROL_ENABLED` | `false` | Allow mouse/keyboard control |
| `GUIALITA_REQUIRE_CONFIRMATION` | `true` | Flag destructive commands |

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/agent/turn` | Send a text/voice turn |
| `GET`  | `/api/agent/audio?path=…` | Stream a TTS artifact |
| `POST` | `/api/agent/stop` | Engage emergency stop (`{action:"stop"}`) |
| `POST` | `/api/agent/stop` | Resume (`{action:"resume"}`) |
| `GET`  | `/api/agent/stop` | Read stop state |
| `GET`  | `/api/agent/memory?action=sessions` | List recent sessions |
| `GET`  | `/api/agent/memory?action=search&q=…` | Search messages |
| `GET`  | `/api/agent/memory?action=events&sessionId=…` | Session event log |
| `GET`  | `/api/agent/memory?action=context&q=…` | Retrieval for Agent Workers |
| `GET`  | `/api/agent/memory?action=session&sessionId=…` | Full session |
| `GET`  | `/api/agent/memory?action=tools` | Tool catalog |
| `GET`  | `/api/agent/memory?action=config` | Active config |
| `POST` | `/api/desktop/screenshot` | Capture a fresh screenshot |
| `GET`  | `/api/desktop/screenshot?path=…` | Stream a screenshot artifact |
| `GET`  | `/api/health` | Web tier healthcheck |

## Filesystem layout

```
data/
├── wrack.sqlite          # SQLite-backed WRACK store
├── logs/
│   └── gui_alita.log     # Structured JSONL agent log
└── artifacts/
    ├── screenshots/      # Captured desktops (PNG)
    ├── audios/           # TTS outputs (WAV)
    ├── documents/        # Files written by write_file tool
    └── agent_outputs/    # Misc agent outputs
```

## Logs

Every important action — startup, model load, intent, plan, tool call,
tool result, error, memory write, retrieval, agent state transition,
safety block — goes through `log.ts` and lands in `data/logs/gui_alita.log`
as JSONL. The same line is mirrored to stdout in a human-readable
form.

## Enabling real LFM models

When a Liquid-AI `llama.cpp` build is available on the host:

```bash
# 1. Make the binary available on PATH
export PATH="$HOME/liquid-audio/build/bin:$PATH"
which llama-liquid-audio

# 2. Tell GUIALITA where the GGUF/mmproj live
export GUIALITA_AUDIO_PROVIDER=local-llama-liquid-audio
export GUIALITA_AUDIO_MODEL_PATH=/opt/models/LFM2.5-Audio-1.5B-Q4.gguf
export GUIALITA_VISION_PROVIDER=local-llama-mtmd
export GUIALITA_VISION_MODEL_PATH=/opt/models/LFM2.5-VL-3B-Q4.gguf
export GUIALITA_VISION_MMPROJ_PATH=/opt/models/LFM2.5-VL-3B-mmproj.gguf

# 3. (Optional) plug an LFM2.5 text chat model as the agent backend
export GUIALITA_AGENT_PROVIDER=local-llama-text
export GUIALITA_AGENT_ENDPOINT=http://127.0.0.1:8082

# 4. Turn desktop control on if xdotool is installed
export GUIALITA_CONTROL_ENABLED=true

# 5. Restart
./run_gui_alita.sh
```

The agent, audio, vision, and tool code does not change. The
`LocalLfmAudioEngine`, `LocalLfmVlEngine`, and `LocalTextBackend` will
be picked up automatically.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| TTS returns 6 KiB silent WAV | stub backend (no LFM model on host) | install LFM2.5-Audio and set `GUIALITA_AUDIO_PROVIDER=local-llama-liquid-audio` |
| Screenshots are gradient PNGs | headless host, no display server | expected; install scrot/gnome-screenshot or run on a desktop |
| Mouse/keyboard no-op | `GUIALITA_CONTROL_ENABLED=false` or no `xdotool` | install xdotool and set the env var |
| Emergency stop blocks every request | `POST /api/agent/stop` with `action:stop` was called | POST `action:resume`, or send `{text:"resume"}` to `/api/agent/turn` |
| Tests fail with `tsc` errors | stale build | `rm -rf .next data && npm run build` |
