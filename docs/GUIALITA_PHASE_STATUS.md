# GUIALITA — Phase Status Matrix

Kompakte lesbare Phasenmatrix. Verbindliche Quelle: `docs/GUIALITA_STATE.yaml`; diese Datei ist nur eine Ansicht.

| Phase | Status      | Scope                                    | Authorization                   |
| ----- | ----------- | ---------------------------------------- | ------------------------------- |
| 0     | PASS        | foundation                               | complete                        |
| 0.5   | PASS        | LFM connection/runtime baseline          | complete                        |
| 1A    | PASS        | microphone → validated WAV               | complete                        |
| 1B    | PASS        | WAV → LFM2.5 Audio → transcription       | complete                        |
| MEM   | PASS        | SQLite Session + Message + ChatService   | complete                        |
| MEM-R | PASS        | Deterministic Feature-Hashing Retrieval  | complete                        |
| MEM-G | PASS        | Persistent Graph (Entities + Relations)  | complete                        |
| GRAPH-V | PASS      | SVG Graph Visualization                  | complete                        |
| TTS     | PASS      | LFM2.5-Audio TTS Output                  | complete                        |
| 1C    | NOT_STARTED | Voice → LFM → TTS                        | explicit authorization required |
| 2     | UNKNOWN     | do not infer                             | not authorized                  |

## Invarianzen

```text
PHASE 0         = PASS
PHASE 0.5       = PASS
PHASE 1A        = PASS
PHASE 1B        = PASS
MEMORY          = PASS
MEMORY_RETR     = PASS
MEMORY_GRAPH    = PASS
GRAPH_VIS       = PASS
TTS             = PASS
PHASE 1C        = NOT_STARTED

CURRENT_BASELINE  = GUIALITA-TTS-V1-PASS
PHASE_1C_AUTH     = REQUIRED
HARD_STOP         = TRUE
```

Phase 2 ist durch keine Repository-Evidenz definiert und wird deshalb als
`UNKNOWN` geführt (nicht als `FROZEN`). Es wird nicht spekuliert, was Phase 2
umfassen würde.

## Hinweise

- `NOT_STARTED` bei 1C bedeutet: Es existiert KEINE Phase-1C-Implementierung,
  keine Voice→LFM→TTS-Schleife.
- Die Existenz von WAV-Dateien in `audio/inbox/` oder `audio/processed/` ist
  KEINE Autorisierung für Phase 1C.
- HARD STOP gilt, bis eine explizite Freigabe erteilt wird.