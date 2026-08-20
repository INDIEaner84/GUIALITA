"""GUIALITA Memory Graph Foundation - Deterministischer Entity-Extractor.

Extrahiert Entitäten und Beziehungen aus Memory-Inhalten.
Kein LLM, keine neuronale Verarbeitung. Rein regelbasiert.

Methoden:
  1. Wortschatz-Abgleich (konfigurierbare bekannte Begriffe)
  2. Anführungszeichen-Extraktion ("Term" oder „Term")
  3. Datei-Pfad-Erkennung
  4. Konservative Großbuchstaben-Erkennung (kein Satzanfang)

Jede Extraktion enthält extraction_version für späteren Austausch.
False positives sind dokumentiert und akzeptabel.
"""

import logging
import os
import re
from typing import Dict, List, Optional, Set, Tuple

log = logging.getLogger("guialita.memory.graph.extractor")

EXTRACTION_VERSION = 1

# Known GUIALITA entities (canonical name → entity_type)
KNOWN_ENTITIES: Dict[str, str] = {
    "GUIALITA": "project",
    "GUIALITA Memory Foundation": "project",
    "granite": "model",
    "granite-3b": "model",
    "Granite-3B": "model",
    "Granite 3B": "model",
    "lfm-audio": "model",
    "LFM2.5-Audio": "model",
    "LFM2.5-Audio-1.5B": "model",
    "lfm-audio-1.5b": "model",
    "ollama": "tool",
    "Ollama": "tool",
    "whisper": "tool",
    "whisper.cpp": "tool",
    "whisper-cli": "tool",
    "espeak-ng": "tool",
    "espeak": "tool",
    "piper": "tool",
    "Piper": "tool",
    "numpy": "tool",
    "sqlite3": "tool",
    "SQLite": "tool",
    "FastAPI": "tool",
    "fastapi": "tool",
    "llama-cpp-python": "tool",
    "llama.cpp": "tool",
    "llama-liquid-audio-cli": "tool",
    "Liquid AI": "tool",
    "PyTorch": "tool",
    "torch": "tool",
    "Hugging Face": "tool",
    "HuggingFace": "tool",
    "PulseAudio": "tool",
    "Linux": "platform",
    "CUDA": "platform",
    "GPU": "platform",
    "GTX 1080 Ti": "hardware",
    "ZOOM H2n": "hardware",
    "USB": "hardware",
    "GUIALITA State": "concept",
    "GUIALITA Phase Status": "concept",
    "Session": "concept",
    "Memory": "concept",
    "MemoryStore": "concept",
    "ChatService": "concept",
    "ModelManager": "concept",
    "MemoryRetriever": "concept",
    "MemoryIndexer": "concept",
    "ContextBuilder": "concept",
}

# Sentence start abbreviations to skip for proper-name detection
_SENTENCE_STARTERS = {
    "der", "die", "das", "ein", "eine", "den", "dem", "des",
    "the", "a", "an", "this", "that", "if", "when", "where",
    "what", "how", "why", "who", "which",
    "ich", "du", "er", "sie", "es", "wir", "ihr",
    "i", "you", "he", "she", "it", "we", "they",
    "ja", "nein", "ok", "halt", "nun", "also", "dann",
    "yes", "no", "well", "now", "so", "then",
}

# Relation patterns: (pattern on content, relation_type)
_RELATION_PATTERNS: List[Tuple[str, str]] = [
    (r"\buses?\b", "uses"),
    (r"\butilizes?\b", "uses"),
    (r"\buses?\b", "uses"),
    (r"\bist\b", "is_a"),
    (r"\bis\b", "is_a"),
    (r"\bhat\b", "has"),
    (r"\bhas\b", "has"),
    (r"\benthält\b", "has"),
    (r"\bcontains\b", "has"),
    (r"\bteilt\b", "related_to"),
    (r"\bshares?\b", "related_to"),
]

# File path pattern
_PATH_PATTERN = re.compile(r"[/\\][\w./\\-]{3,}")

# Quote patterns (German and English)
_QUOTE_PATTERN_EN = re.compile(r'"([^"]{2,60})"')
_QUOTE_PATTERN_DE = re.compile(r'„([^"]{2,60})"')


def _normalize_name(name: str) -> str:
    """Normalisiert einen Entity-Namen für Konsistenz."""
    return name.strip()


def extract_entities(text: str) -> List[Dict]:
    """Extrahiert Entitäten aus einem Text.

    Liefert Liste von dicts: {canonical_name, entity_type, extraction_version}
    Dedupliziert innerhalb des Aufrufs.
    """
    if not text or not text.strip():
        return []

    found: Dict[str, str] = {}  # canonical_name → entity_type

    # 1. Wortschatz-Abgleich (längste Übereinstimmung zuerst)
    text_lower = text.lower()
    for canonical, etype in sorted(KNOWN_ENTITIES.items(), key=lambda x: -len(x[0])):
        if canonical.lower() in text_lower:
            if canonical not in found:
                found[canonical] = etype

    # 2. Anführungszeichen-Extraktion
    for match in _QUOTE_PATTERN_EN.finditer(text):
        term = match.group(1).strip()
        if len(term) >= 2 and term not in found:
            found[term] = "concept"
    for match in _QUOTE_PATTERN_DE.finditer(text):
        term = match.group(1).strip()
        if len(term) >= 2 and term not in found:
            found[term] = "concept"

    # 3. Datei-Pfade
    for match in _PATH_PATTERN.finditer(text):
        path = match.group(0).strip()
        if len(path) >= 5 and path not in found:
            found[path] = "path"

    # 4. Konservative Großbuchstaben-Erkennung
    # Nur Wörter die mit Großbuchstaben beginnen UND nicht nach Satzzeichen stehen
    # UND nicht in der Stopword-Liste sind
    words = re.split(r'\s+', text)
    for i, word in enumerate(words):
        clean = re.sub(r'[^\w]', '', word)
        if not clean or len(clean) < 3:
            continue
        if not clean[0].isupper():
            continue
        # Prüfe ob es ein Satzanfang ist
        if i > 0:
            prev_word = re.sub(r'[^\w]', '', words[i - 1])
            if prev_word.lower() in _SENTENCE_STARTERS:
                continue
            # Prüfe ob vorheriges Wort Satzzeichen enthält
            if any(c in words[i - 1] for c in ".!?"):
                continue
        # Skip wenn es bereits als bekanntes Entity gefunden wurde
        if clean in found or clean.lower() in {k.lower() for k in found}:
            continue
        # Skip wenn es eine Zahl ist
        if clean.isdigit():
            continue
        # Konservativ: nur wenn es wie ein Eigenname aussieht
        if clean[0].isupper() and not clean.isupper():
            found[clean] = "concept"

    result = []
    for canonical, etype in found.items():
        result.append({
            "canonical_name": canonical,
            "entity_type": etype,
            "extraction_version": EXTRACTION_VERSION,
        })
    return result


def extract_relations(text: str, entity_names: Set[str]) -> List[Dict]:
    """Extrahiert Beziehungen zwischen bekannten Entitäten im Text.

    Args:
        text: Memory-Inhalt
        entity_names: Menge der canonical_names der gefundenen Entitäten

    Liefert Liste von dicts:
        {source_name, relation_type, target_name, extraction_version}
    """
    if not text or not entity_names or len(entity_names) < 2:
        return []

    text_lower = text.lower()
    entity_list = sorted(entity_names, key=len, reverse=True)
    relations: List[Dict] = []
    seen: Set[Tuple[str, str, str]] = set()

    # 1. Pattern-basierte Beziehungen
    for pattern, rel_type in _RELATION_PATTERNS:
        if re.search(pattern, text_lower):
            # Finde Entity-Paare die im Text zusammen vorkommen
            for i, e1 in enumerate(entity_list):
                if e1.lower() not in text_lower:
                    continue
                for e2 in entity_list[i + 1:]:
                    if e2.lower() not in text_lower:
                        continue
                    key = (e1, rel_type, e2)
                    if key not in seen:
                        seen.add(key)
                        relations.append({
                            "source_name": e1,
                            "relation_type": rel_type,
                            "target_name": e2,
                            "extraction_version": EXTRACTION_VERSION,
                        })

    # 2. Co-occurrence: zwei Entitäten im selben Text → related_to
    present = [e for e in entity_list if e.lower() in text_lower]
    for i, e1 in enumerate(present):
        for e2 in present[i + 1:]:
            key = (e1, "related_to", e2)
            if key not in seen:
                seen.add(key)
                relations.append({
                    "source_name": e1,
                    "relation_type": "related_to",
                    "target_name": e2,
                    "extraction_version": EXTRACTION_VERSION,
                })

    return relations


def extract_from_memory(memory_content: str) -> Tuple[List[Dict], List[Dict]]:
    """Extrahiert Entitäten und Beziehungen aus einem Memory-Inhalt.

    Liefert (entities, relations).
    """
    entities = extract_entities(memory_content)
    entity_names = {e["canonical_name"] for e in entities}
    relations = extract_relations(memory_content, entity_names)
    return entities, relations
