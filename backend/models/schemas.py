from typing import Optional, List

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    status: str
    response: str
    model: str
    latency_ms: float
    runtime: str = ""
    session_id: str = ""
    message_id: str = ""
    history_used: int = 0
    history_limit: int = 0
    retrieval: Optional[dict] = None


class SessionResponse(BaseModel):
    session_id: str
    status: str = "ACTIVE"
    title: str = "Neue Session"
    created_at: str = ""
    updated_at: str = ""


class ErrorResponse(BaseModel):
    status: str = "error"
    error: str
    model: str = ""
    runtime: str = ""
    details: str = ""


class MemoryStatusResponse(BaseModel):
    enabled: bool
    embedding_version: int
    memory_count: int
    database_available: bool
    entity_count: int = 0
    relation_count: int = 0
    error: str = ""


class MemorySearchResult(BaseModel):
    memory_id: str
    source_message_id: str
    session_id: str
    content: str
    score: float
    reason: str = ""
    created_at: str = ""


class MemorySearchResponse(BaseModel):
    status: str
    count: int
    results: List[MemorySearchResult] = []


class AudioStatusResponse(BaseModel):
    status: str
    engine: str
    runtime: str
    model: str = ""
    model_size_gb: float = 0.0
    gpu: bool = False
    language: str = "auto"
    sample_rate: int = 16000
    error: str = ""


class AudioTranscribeResponse(BaseModel):
    status: str
    transcript: str = ""
    language: str = "auto"
    duration_s: float = 0.0
    transcription_ms: float = 0.0
    engine: str = ""
    runtime: str = ""
    model: str = ""
    error: str = ""


class AudioChatRequest(BaseModel):
    """JSON payload for the complete audio → STT → chat pipeline."""
    audio: str = Field(min_length=1, max_length=35_000_000)
    duration_s: float = Field(default=0.0, ge=0.0, le=180.0)
    model: Optional[str] = None
    session_id: Optional[str] = None


class AudioChatResponse(BaseModel):
    status: str
    transcript: str = ""
    response: str = ""
    model: str = ""
    language: str = "auto"
    recording_s: float = 0.0
    transcription_ms: float = 0.0
    chat_ms: float = 0.0
    total_ms: float = 0.0
    stt_runtime: str = ""
    chat_runtime: str = ""
    session_id: str = ""
    message_id: str = ""
    history_used: int = 0
    error: str = ""
    details: str = ""
