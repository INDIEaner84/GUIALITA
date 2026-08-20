import logging
import os
import sys
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from backend.manager import ModelManager
from backend.memory.store import MemoryStore
from backend.chat_service import ChatService
from backend.models.schemas import (ChatRequest, ChatResponse, ErrorResponse, AudioStatusResponse, AudioTranscribeResponse, AudioChatResponse, SessionResponse, MemoryStatusResponse, MemorySearchResponse, MemorySearchResult)
from backend.memory.retrieval import GraphRetriever
from backend.utils.latency import Latency
from backend.audio.tts import tts_service
from backend.audio.voice_activation import VoiceActivationService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("guialita")

app = FastAPI(title="GUIALITA - Local LFM Assistant", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ModelManager()
store = MemoryStore()
chat_service = ChatService(manager, store)
graph_retriever = GraphRetriever(store)
voice_activation = VoiceActivationService(manager=manager, chat_service=chat_service, tts_service=tts_service)

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


@app.get("/health")
def health():
    t0 = time.perf_counter()
    h = manager.health()
    h["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    return h


@app.get("/models")
def list_models():
    return {"models": manager.list_models()}


@app.get("/audio/status")
def audio_status():
    return AudioStatusResponse(
        status=manager.stt_health()["status"],
        engine=manager.stt_health()["engine"],
        runtime=manager.stt_health()["runtime"],
        model=manager.stt_health().get("model", ""),
        model_size_gb=manager.stt_health().get("model_size_gb", 0.0),
        gpu=manager.stt_health().get("gpu", False),
        language=manager.stt_health()["language"],
        sample_rate=manager.stt_health()["sample_rate"],
        error=manager.stt_health().get("error", ""),
    ).model_dump()


@app.post("/audio/transcribe")
async def audio_transcribe(request: Request):
    """Transkribiert eine WAV-Aufnahme (Raw-Body, Content-Type: audio/wav).

    Browser zeichnet PCM 16 kHz mono auf und sendet die WAV-Bytes direkt.
    """
    content_type = request.headers.get("content-type", "").lower()
    if "wav" not in content_type and "octet-stream" not in content_type:
        return JSONResponse(
            status_code=415,
            content=AudioTranscribeResponse(
                status="error",
                error="unsupported_media_type",
                details=f"Erwartet audio/wav, erhalten: {content_type}",
            ).model_dump(),
        )

    body = await request.body()
    max_bytes = int(manager.stt_config.get("max_audio_bytes", 25_000_000))
    if len(body) < 100:
        return JSONResponse(
            status_code=400,
            content=AudioTranscribeResponse(
                status="error",
                error="empty_audio",
                details="Audio-Body ist leer oder zu kurz (<100 Bytes)",
            ).model_dump(),
        )
    if len(body) > max_bytes:
        return JSONResponse(
            status_code=413,
            content=AudioTranscribeResponse(
                status="error",
                error="audio_too_large",
                details=f"Audio zu gross: {len(body)} Bytes (max {max_bytes})",
            ).model_dump(),
        )

    # WAV-Header pruefen (RIFF....WAVE)
    if not (body[:4] == b"RIFF" and body[8:12] == b"WAVE"):
        return JSONResponse(
            status_code=400,
            content=AudioTranscribeResponse(
                status="error",
                error="invalid_audio_format",
                details="Kein gültiger WAV-Header (RIFF/WAVE erwartet)",
            ).model_dump(),
        )

    if not manager.stt.is_available():
        return JSONResponse(
            status_code=503,
            content=AudioTranscribeResponse(
                status="error",
                error="stt_unavailable",
                details="whisper.cpp oder Modell nicht verfügbar",
            ).model_dump(),
        )

    t0 = time.perf_counter()
    try:
        result = manager.transcribe(body)
        t1 = time.perf_counter()
        return AudioTranscribeResponse(
            status="success",
            transcript=result["transcript"],
            language=manager.stt_config.get("language", "auto"),
            duration_s=round(_wav_duration(body), 3),
            transcription_ms=round((t1 - t0) * 1000.0, 2),
            engine=result["engine"],
            runtime=result["runtime"],
            model=result["model"],
        ).model_dump()
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=AudioTranscribeResponse(
                status="error",
                error=str(e),
                details=f"{type(e).__name__}: {e}",
            ).model_dump(),
        )


@app.post("/audio/chat")
async def audio_chat(request: Request):
    """Audio → STT → bestehende Chat-Pipeline in einem Schritt.

    Erwartet JSON: { "audio": "<base64-wav>", "duration_s": 3.2, "model": "granite-3b" }
    """
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content=AudioChatResponse(status="error", error="invalid_json", transcript="", response="", model="").model_dump())

    import base64
    try:
        wav_bytes = base64.b64decode(data.get("audio", ""))
    except Exception:
        return JSONResponse(status_code=400, content=AudioChatResponse(status="error", error="invalid_base64", transcript="", response="", model="").model_dump())

    if len(wav_bytes) < 100:
        return JSONResponse(status_code=400, content=AudioChatResponse(status="error", error="empty_audio", transcript="", response="", model="").model_dump())

    recording_s = float(data.get("duration_s", 0.0))
    t0 = time.perf_counter()

    try:
        result = manager.transcribe(wav_bytes)
    except Exception as e:
        return JSONResponse(status_code=500, content=AudioChatResponse(status="error", error="stt_failed", transcript="", response="", model="", details=f"{type(e).__name__}: {e}").model_dump())

    t1 = time.perf_counter()
    transcription_ms = round((t1 - t0) * 1000.0, 2)
    transcript = result["transcript"]

    # Transcript an bestehende Chat-Pipeline uebergeben
    try:
        chat_result = manager.chat(transcript, data.get("model") or None, temperature=0.7)
    except Exception as e:
        return JSONResponse(status_code=500, content=AudioChatResponse(
            status="error", error="chat_failed", transcript=transcript, response="",
            model=data.get("model") or manager.default_model,
            transcription_ms=transcription_ms,
            details=f"{type(e).__name__}: {e}",
        ).model_dump())

    t2 = time.perf_counter()
    return AudioChatResponse(
        status="success",
        transcript=transcript,
        response=chat_result["response"],
        model=chat_result["model"],
        language=manager.stt_config.get("language", "auto"),
        recording_s=recording_s,
        transcription_ms=transcription_ms,
        chat_ms=round(chat_result.get("latency_ms", 0.0), 2),
        total_ms=round((t2 - t0) * 1000.0, 2),
        stt_runtime=result["runtime"],
        chat_runtime=chat_result.get("runtime", "llamacpp"),
    ).model_dump()


def _wav_duration(data: bytes) -> float:
    """Bestimmt die Dauer aus dem WAV-Header (SampleRate + Data-Chunk)."""
    try:
        import struct
        if len(data) < 44:
            return 0.0
        sample_rate = struct.unpack("<I", data[24:28])[0]
        # Data-Chunk groesse an Position 40 (standard PCM)
        data_size = struct.unpack("<I", data[40:44])[0]
        if sample_rate <= 0:
            return 0.0
        return data_size / 2 / sample_rate if data_size else 0.0
    except Exception:
        return 0.0


@app.post("/sessions")
def create_session():
    session = store.create_session()
    return SessionResponse(
        session_id=session["id"],
        status=session["status"],
        title=session["title"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
    ).model_dump()


@app.get("/sessions")
def list_sessions(limit: int = 50):
    return {"sessions": store.list_sessions(limit=limit)}


@app.get("/sessions/{session_id}/messages")
def session_messages(session_id: str, limit: int = None):
    session = store.get_session(session_id)
    if session is None:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(error="unknown_session", details=f"Session existiert nicht: {session_id}").model_dump(),
        )
    return {
        "session": session,
        "messages": store.get_messages(session_id, limit=limit),
        "count": store.count_messages(session_id),
    }


@app.post("/chat")
def chat(req: ChatRequest, request: Request):
    if not req.message or not req.message.strip():
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="empty_message",
                details="message darf nicht leer sein",
                runtime="api",
            ).model_dump(),
        )

    # Modell vorab validieren (404-Semantik bleibt erhalten, keine Persistenz vor Validierung)
    if req.model:
        try:
            manager.get_model_cfg(req.model)
        except KeyError:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error="unknown_model",
                    model=req.model,
                    runtime="api",
                    details="Verfuegbare Modelle: " + ", ".join(m["id"] for m in manager.list_models()),
                ).model_dump(),
            )

    lat = Latency()
    try:
        lat.mark_model_request()
        result = chat_service.chat(
            req.message,
            req.model,
            session_id=req.session_id,
            temperature=0.7,
        )
        lat.mark_model_response()
        return ChatResponse(
            status="success",
            response=result["response"],
            model=result["model"],
            latency_ms=round(result.get("latency_ms", lat.total_ms), 2),
            runtime=result.get("runtime", "llamacpp"),
            session_id=result["session_id"],
            message_id=result["message_id"],
            history_used=result.get("history_used", 0),
            history_limit=result.get("history_limit", 0),
            retrieval=result.get("retrieval"),
        ).model_dump()
    except KeyError as e:
        lat.mark_model_response()
        msg = str(e)
        if msg.startswith("Unbekannte Session"):
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error="unknown_session",
                    runtime="api",
                    details=msg,
                ).model_dump(),
            )
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error="unknown_model",
                model=str(e).replace("Unbekanntes Modell: ", "").strip("'"),
                runtime="api",
                details="Verfuegbare Modelle: " + ", ".join(m["id"] for m in manager.list_models()),
            ).model_dump(),
        )
    except FileNotFoundError as e:
        lat.mark_model_response()
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="model_not_found",
                model=req.model or manager.default_model,
                runtime="llamacpp",
                details=f"Modell-Datei fehlt: {e.filename}",
            ).model_dump(),
        )
    except Exception as e:
        lat.mark_model_response()
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=str(e),
                model=req.model or manager.default_model,
                runtime="llamacpp",
                details=f"{type(e).__name__}: {e}",
            ).model_dump(),
        )


@app.get("/memory/status")
def memory_status():
    try:
        st = chat_service.status()
        return MemoryStatusResponse(
            enabled=st["enabled"],
            embedding_version=st["embedding_version"],
            memory_count=st["memory_count"],
            database_available=st["database_available"],
            entity_count=store.count_entities(),
            relation_count=store.count_relations(),
        ).model_dump()
    except Exception as e:
        return MemoryStatusResponse(
            enabled=False, embedding_version=0, memory_count=0,
            database_available=False, error=str(e),
        ).model_dump()


@app.get("/memory/graph/{entity_name}")
def memory_graph(entity_name: str):
    try:
        result = graph_retriever.traverse(entity_name)
        if result["entity"] is None:
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "error": "unknown_entity",
                    "details": f"Entität '{entity_name}' nicht gefunden",
                    "entity_count": result["entity_count"],
                    "relation_count": result["relation_count"],
                },
            )
        return {
            "status": "success",
            "entity": result["entity"],
            "outgoing": result["outgoing"],
            "incoming": result["incoming"],
            "entity_count": result["entity_count"],
            "relation_count": result["relation_count"],
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)},
        )


@app.get("/memory/graph")
def memory_graph_full(max_nodes: int = 100, max_edges: int = 250):
    try:
        graph = store.get_bounded_graph(
            max_nodes=min(max_nodes, 500),
            max_edges=min(max_edges, 1000),
        )
        return {"status": "success", **graph}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)},
        )


@app.post("/memory/search")
async def memory_search(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": "invalid_json"},
        )

    query = data.get("query", "")
    if not query:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": "empty_query", "details": "query darf nicht leer sein"},
        )

    top_k = data.get("top_k", 4)
    session_id = data.get("session_id")

    try:
        results = chat_service.search(query, top_k=top_k, session_id=session_id)
        return MemorySearchResponse(
            status="success",
            count=len(results),
            results=[MemorySearchResult(**r) for r in results],
        ).model_dump()
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)},
        )


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/graph")
def graph_view():
    return FileResponse(os.path.join(FRONTEND_DIR, "graph.html"))


@app.get("/audio/voice/status")
def audio_voice_status():
    return voice_activation.status()


@app.post("/audio/voice/start")
def audio_voice_start():
    voice_activation.start()
    return {"status": "success", "message": "Voice Activation gestartet"}


@app.post("/audio/voice/stop")
def audio_voice_stop():
    voice_activation.stop()
    return {"status": "success", "message": "Voice Activation gestoppt"}


@app.get("/audio/tts/status")
def audio_tts_status():
    return tts_service.health()


@app.post("/audio/tts")
async def audio_tts(request: Request):
    body = await request.json()
    text = body.get("text", "").strip()
    voice = body.get("voice")
    if not text:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": "text_required", "details": "Text darf nicht leer sein"},
        )
    try:
        result = tts_service.synthesize(text, voice)
        from fastapi.responses import Response
        return Response(
            content=result["wav_bytes"],
            media_type="audio/wav",
            headers={
                "X-TTS-Voice": result["voice"],
                "X-TTS-Duration-S": str(result["duration_s"]),
                "X-TTS-Latency-Ms": str(result["latency_ms"]),
                "X-TTS-Sample-Rate": str(result["sample_rate"]),
            },
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": "invalid_request", "details": str(e)},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": "tts_failed", "details": str(e)},
        )


@app.on_event("shutdown")
def shutdown():
    manager.close()
    store.close()


if __name__ == "__main__":
    import uvicorn

    cfg = manager._config.get("server", {})
    uvicorn.run(app, host=cfg.get("host", "0.0.0.0"), port=int(cfg.get("port", 8080)))
