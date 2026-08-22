# GUIALITA — Phase Status View

Verbindliche Quelle: `docs/GUIALITA_STATE.yaml`. Diese Datei ist eine lesbare
Ansicht und darf nicht als separate Statusquelle behandelt werden.

| Bereich | Status | Hinweis |
|---|---|---|
| Phase 0 / 0.5 | PASS | lokales LLM-Backend und Runtime-Basis |
| Phase 1A | PASS | Mikrofon → validierte WAV |
| Phase 1B | PASS | WAV → STT → Transkript |
| Phase 1C | PASS | Voice → STT → Chat → TTS, Batch-Pipeline |
| Memory Session | PASS | SQLite-Sessions und Nachrichten |
| Memory Retrieval | PASS | deterministisches Retrieval |
| Memory Graph | PASS | Entities und Relations |
| Graph Visualization | PASS | SVG-Ansicht |
| TTS | PASS | LFM2.5-Audio TTS, Runtime-abhängig |
| M4 Testharness | PASS | 46 isolierte Tests |
| M5 Audit/Export | PASS | JSONL, JSON- und Markdown-Export |
| M5 Performance/Diagnostics | IN_PROGRESS | Benchmark vorhanden, Runtime-Messung offen |
| Vision | NOT_STARTED | nur Prototypen, nicht kanonisch aktiviert |
| Desktop Control | NOT_STARTED | Sicherheitsdesign erforderlich |

## Aktuelle Einschränkungen

- Vollständige Runtime-Tests benötigen lokale Modelle und Runtimes.
- Echte Mikrofon-/Lautsprecher-Abnahme benötigt den Zielrechner.
- Deutsche STT-Qualität und Voice-Latenz sind noch nicht vollständig abgenommen.
- Vision und Desktop-Control führen noch keine kanonischen Aktionen aus.

## Statusdefinitionen

- `PASS`: implementiert und durch vorhandene Evidenz beziehungsweise isolierte
  Tests belegt.
- `IN_PROGRESS`: Teile implementiert, weitere Messung oder Stabilisierung offen.
- `NOT_STARTED`: nicht in die kanonische Anwendung integriert.
- `BLOCKED`: Umsetzung oder Verifikation wartet auf eine externe Voraussetzung.
