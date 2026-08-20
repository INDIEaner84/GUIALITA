# GUIALITA — Architecture

> **Spec version:** PHASE 2–7 of the brief, adapted to the headless sandbox
> described in `docs/FORENSIC_BOOTSTRAP.md`.

## Layered architecture

The project honours the layering from the brief (§7) verbatim:

```
┌──────────────────────────────────────────────────────────────────┐
│ UI  (React + Tailwind, Next.js App Router)                        │
│   • Conversation view   • Mic / Speak   • Screen view             │
│   • STOP AGENT button   • WRACK session sidebar   • Config panel  │
└──────────────────────────────────────────────────────────────────┘
                              │ HTTP /api/agent/*
┌──────────────────────────────────────────────────────────────────┐
│ Agent Core (TypeScript, server-only)                              │
│   intent.ts → planner.ts → loop.ts (Observe · Plan · Act · Verify │
│             · Recover) → text_backend.ts (compose final reply)   │
└──────────────────────────────────────────────────────────────────┘
              │                                            │
┌──────────────────────────────┐    ┌──────────────────────────────┐
│ Multimodal Layer             │    │ Tool Layer (typed, zod)       │
│   audio/engine.ts (LFM2.5-A) │    │   tools/router.ts            │
│   vision/engine.ts (LFM2.5-VL)│   │  - screenshot  - mouse_*    │
│   backends: stub | local-…   │    │  - keyboard_*  - terminal_  │
└──────────────────────────────┘    │  - read/write/list file     │
              │                     └──────────────────────────────┘
              │                                │
              │                  ┌──────────────────────────────┐
              │                  │ Desktop Engine                │
              │                  │   desktop/engine.ts           │
              │                  │   (scrot/import/mss/fallback) │
              │                  └──────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│ Safety (safety.ts)                                               │
│   • tool allowlist, dangerous-command regex, /etc|/proc guard     │
│   • destructive-action flag for UI confirmation                   │
│   • global emergency stop checked between every step              │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│ WRACK — Working Retrieval And Context Knowledge                   │
│   memory/store.ts: Session · Message · Task · Event · Observation │
│                   · ToolCall · ToolResult · Artifact              │
│   storage: SQLite (better-sqlite3) + filesystem artifact store    │
│   typed retrieval API for future Agent Workers                    │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│ Model Layer (pluggable)                                           │
│   audio:  "stub" | "local-llama-liquid-audio" | "cloud"           │
│   vision: "stub" | "local-llama-mtmd"           | "cloud"         │
│   agent:  "stub" | "local-llama-text"          | "cloud"          │
└──────────────────────────────────────────────────────────────────┘
```

Every layer is replaceable. The agent loop never imports a specific
runtime; it only sees the Audio / Vision / Tool interfaces.

## Backend selection

`src/gui_alita/config.ts` is the single source of truth. Backends are
chosen by env vars:

```
GUIALITA_AUDIO_PROVIDER=stub | local-llama-liquid-audio | cloud
GUIALITA_VISION_PROVIDER=stub | local-llama-mtmd | cloud
GUIALITA_AGENT_PROVIDER=stub | local-llama-text | cloud
GUIALITA_AUDIO_MODEL_PATH=/path/to/LFM2.5-Audio-1.5B-Q4.gguf
GUIALITA_VISION_MODEL_PATH=/path/to/LFM2.5-VL-3B-Q4.gguf
GUIALITA_VISION_MMPROJ_PATH=/path/to/LFM2.5-VL-3B-mmproj.gguf
GUIALITA_AGENT_ENDPOINT=http://127.0.0.1:8082
```

In the headless sandbox all providers are `stub`; the LFM adapters
exist in the code and are activated the moment a model is available
on disk.

## WRACK data model

`Session ─┬─ Message
          ├─ Task ─┬─ PlanStep[]
          │        └─ result
          └─ Event ─┬─ tool | type | status | arguments | result
                   └─ taskId (FK)

Artifact → path on disk, sha256, mime, kind ∈ {screenshot, audio, document, log, agent_output}.

`getRelatedContext(query)` is the retrieval entry-point for Agent
Workers. It returns the most relevant messages, sessions, and events
for a query, suitable for prompt construction.

## Agent loop

```
USER REQUEST
   ↓
UNDERSTAND  (intent.ts: classifyIntent)
   ↓
PLAN       (planner.ts: planFor → PlanStep[])
   ↓
for each step:
   OBSERVE  (screenshot when needed)
   ACT      (dispatchTool → real or noop)
   OBSERVE  (re-screenshot when needed)
   VERIFY   (event="verification")
   if failed → RECOVER (1 retry, mkdir parent etc.)
   ↓
COMPOSE    (text_backend.ts)
   ↓
TTS        (AudioEngine.synthesize → artifact)
   ↓
RESPOND    (next.js HTTP + WebSocket-ready JSON)
```

Every state transition writes an `EventRecord` to WRACK. The event log
is append-only, so the agent can later be replayed or audited.

## Safety

* Every tool call passes through `safety.ts:evaluateToolCall`.
* `rm -rf /`, fork bombs, `curl|sh`, `sudo`, `shutdown`, etc. are
  blocked by a regex allowlist.
* Filesystem writes under `/etc`, `/boot`, `/proc`, `/sys` are blocked.
* When `GUIALITA_REQUIRE_CONFIRMATION=true` (the default), commands
  that look destructive are flagged and surfaced in the UI.
* `POST /api/agent/stop` engages an emergency stop that is checked
  between every agent step.
* The UI shows a red `⏹ STOP AGENT` button.

## Graph compatibility

The `events`, `messages`, `tasks`, and `artifacts` tables all carry a
`session_id` foreign key; `events` also carries a `task_id` foreign
key. The store can therefore be walked as a graph
(Session → Message, Session → Event, Session → Task → Event). A
subsequent layer can introduce a real graph store without changing
the agent code.
