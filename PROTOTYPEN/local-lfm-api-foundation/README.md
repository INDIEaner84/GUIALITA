# Local LFM Browser Communication Foundation (Phase 0)

Minimal functional core demonstrating full browser-to-local-LFM communication.

```
BROWSER ──> LOCAL ASSISTANT API ──> LOCAL MODEL ADAPTER ──> NATIVE LFM RUNTIME
   ▲                                                              │
   └────────────────────── LOCAL API RESPONSE ────────────────────┘
```

---

## 1. Prerequisites
- Node.js 18+ & npm
- Python 3.8+ (for local native LFM runtime engine)
- Local PostgreSQL instance (`postgresql://postgres:postgres@127.0.0.1:5432/app_db`)

---

## 2. Required LFM Runtimes & Supported Backends
The system automatically probes and supports multiple local AI backends:
1. **Local LFM Native HTTP Engine** (Default Port: `8000`)
2. **Ollama Local Service** (Default Port: `11434`)
3. **llama.cpp / OpenAI Local Endpoint** (Default Port: `8080`)
4. **Embedded LFM Emulator** (Built-in standalone fallback)

---

## 3. Active Model Configuration
- **Default LFM Model:** `lfm-1.0-3b-instruct`
- **Format:** PyTorch / GGUF
- **Runtime:** `LFM Local Engine 1.0.0`
- **Port:** `8000`

---

## 4. How to Start the Local LFM Model Server
To launch the native local LFM server process on port 8000:

```bash
python3 scripts/lfm_runtime_server.py --port 8000
```

Verify that the local LFM model server is online:
```bash
curl http://127.0.0.1:8000/health
```

Expected JSON response:
```json
{
  "status": "ONLINE",
  "model": "lfm-1.0-3b-instruct",
  "format": "PyTorch/GGUF",
  "runtime": "LFM Local Engine 1.0.0",
  "models": ["lfm-1.0-3b-instruct", "lfm-lite", "lfm-7b-instruct"],
  "port": 8000,
  "loaded": true
}
```

---

## 5. How to Start the Backend API & Next.js App
In a separate terminal window, start the Next.js fullstack application:

```bash
npm run dev
```

Or for production build & start:
```bash
npm run build && npm start
```

---

## 6. How to Open the Browser Interface
Open your web browser and navigate to:
```
http://localhost:3000
```

---

## 7. Performing the Connection Test
### Via Browser UI:
Click the **"LFM CONNECTION TEST"** button in the top right header.
The system will send:
```text
Hallo LFM, antworte mit:
LFM CONNECTION TEST OK
```
The browser interface displays:
- **MODEL**: `lfm-1.0-3b-instruct`
- **REQUEST**: User Prompt
- **RESPONSE**: LFM Response Text
- **LATENCY**: Response time in milliseconds
- **TIMESTAMP**: ISO Timestamp
- **STATUS**: `SUCCESS` / `ONLINE`

### Via Automated CLI Script:
```bash
npx tsx scripts/test_e2e.ts
```

### Via Direct HTTP API:
```bash
curl -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hallo LFM, antworte mit:\nLFM CONNECTION TEST OK"}'
```

---

## 8. Technical Error Diagnostics
If the LFM runtime or API becomes unreachable, the UI and API provide exact diagnostic details:

```text
MODEL STATUS: OFFLINE
REASON: Connection refused at http://127.0.0.1:8000
TARGET: 127.0.0.1:8000
ACTION: Start the LFM runtime with command: python3 scripts/lfm_runtime_server.py --port 8000
```

To fetch live system diagnostics from the backend:
```bash
curl http://localhost:3000/api/diagnostics
```

---

## 9. Phase 0 Verification Checklist

- [x] LFM found & probed
- [x] LFM server running (`python3 scripts/lfm_runtime_server.py --port 8000`)
- [x] API started (`/api/health`, `/api/chat`, `/api/diagnostics`)
- [x] Browser interface operational at `http://localhost:3000`
- [x] Chat interface functional
- [x] Real LFM model response received
- [x] Live status visualization operational (MODEL, API, LATENCY, STATUS)
- [x] Diagnostics drawer working with exact technical failure reasons
- [x] Automated End-to-End test passed (`scripts/test_e2e.ts`)

**FINAL STATUS: PASS**
