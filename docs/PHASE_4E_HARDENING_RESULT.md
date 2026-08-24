# GUIALITA — Phase 4E: Hardening (Doku, Reproduzierbarkeit, Portabilität)

**STATUS**: PASS
**DATUM**: 2026-08-20
**BASELINE VORHER**: GUIALITA-VOICE-ACTIVATION-V1-PASS (Doku widersprüchlich)
**BASELINE NACHHER**: GUIALITA-CUDA-VMM-REPAIR-PASS
**SCOPE**: keine Laufzeitfunktion geändert — nur Konfiguration, Portabilität, Dokumentation

---

## 0. Anlass

Die Statusdokumentation lag in drei Dateien parallel und widersprach sich:
`GUIALITA_STATE.yaml` nannte VOICE-ACTIVATION-V1 als Baseline,
`GUIALITA_PHASE_STATUS.md` und `GUIALITA_SESSION_BOOTSTRAP.md` nannten TTS-V1.
Der CUDA-VMM-Repair vom 2026-08-20 kam in keinem der drei Dokumente vor.
Gleichzeitig war das Projekt an genau eine Maschine gebunden (16 absolute
Pfade im Code) und hatte keine Dependency-Deklaration.

Leitprinzip dieser Phase: **reduzieren statt ergänzen**. Eine Kopie, die
nicht mitgepflegt wird, ist schlimmer als keine Kopie.

---

## 1. Zustandskonsolidierung

`docs/GUIALITA_STATE.yaml` ist ab sofort die **einzige Quelle der Wahrheit**.
Schema v2, mit explizitem Statusvokabular (`PASS`, `OBSERVED`, `DOCUMENTED`,
`OPEN`, `UNKNOWN`, `NOT_STARTED`, `BLOCKED`,
`PERFORMANCE_OPTIMIZATION_REQUIRED`).

Die beiden Duplikate wurden **entkernt statt aktualisiert**:

| Datei | vorher | nachher |
|---|---|---|
| `docs/GUIALITA_PHASE_STATUS.md` | eigene Statusmatrix (veraltet) | Verweis auf STATE.yaml, keine Statusangabe mehr |
| `docs/GUIALITA_SESSION_BOOTSTRAP.md` | eigene Statusliste + Baseline | Onboarding ohne Statusangaben |

Neu im kanonischen Zustand erfasst:

- `cuda_vmm_repair` — **PASS** (fehlte vollständig)
- `voice_forensics_v1` — Untersuchung `PASS`, **Gate `OPEN`**
- `phase_4e_hardening` — PASS
- `stt_architecture` — DOCUMENTED (Verweis auf ADR-001)
- `phase_2_vision` — **UNKNOWN** (nicht zu FROZEN oder PASS umgedeutet)

Baseline-Konflikt aufgelöst: `baseline_history` führt alle vier Baselines
chronologisch, `current_baseline` benennt genau eine. Historische Reports
behalten ihre damalige Baseline-Angabe — sie sind unveränderliche Belege.

**Voice Forensics bleibt bewusst OPEN.** Der CUDA-Repair adressiert die
Hauptursache (LLM auf CPU), aber es existiert keine Nachmessung der
vollständigen Sprachpipeline. Ohne Messung kein Gate-Schluss.

---

## 2. STT-Architekturentscheidung

Neu: `docs/adr/ADR-001-stt-whisper-cpp.md` (ACCEPTED).

Dokumentiert die reale Kette — whisper.cpp (STT) → Granite 4.1 3B
(Kognition) → LFM2.5-Audio (TTS) — mit Begründung (keine Audio-API in
llama-cpp-python, CPU-only-Runner, EN-fokussierte LFM-ASR), Konsequenzen
(~14 s STT-Latenz), verworfenen Alternativen und Revisionsauslösern.

Explizit festgehalten: **LFM2.5-Audio stellt nicht den deutschen
Live-STT-Pfad bereit.** Der frühere Bootstrap-Text legte das Gegenteil nahe.
Der Phase-1B-Batch-ASR-Pfad mit LFM2.5-Audio bleibt davon unberührt.

---

## 3. Reproduzierbarkeit

Neu: `requirements.txt` — abgeleitet aus den tatsächlichen Imports, kein
`pip freeze`. Externe, nicht per pip installierbare Komponenten
(whisper.cpp, llama-liquid-audio-cli, Ollama, Modelldateien) sind darin
benannt statt verschwiegen. CUDA-Bau von llama-cpp-python separat
dokumentiert.

Korrigiert: Die Angabe „numpy 2.5.2" aus dem alten Bootstrap ist unbelegt —
diese Version existiert auf PyPI nicht (höchste: 2.4.x). Ersetzt durch eine
verifizierbare Schranke.

Keine Testabhängigkeit hinzugefügt: die Suiten nutzen `unittest` und `urllib`
aus der Standardbibliothek.

---

## 4. Pfad-Entkopplung

Neu: `backend/paths.py` — ein Ort für alle Pfadentscheidungen, plus
`.env.example` (die reale `.env` ist nicht versioniert).

| Variable | Default |
|---|---|
| `GUIALITA_ROOT` | Repository-Wurzel |
| `GUIALITA_MODEL_ROOT` | `$GUIALITA_ROOT/models` |
| `GUIALITA_EXTERNAL_MODEL_ROOT` | `$GUIALITA_MODEL_ROOT` |
| `GUIALITA_RUNTIME_ROOT` | `$GUIALITA_ROOT/runtime` |
| `GUIALITA_DATA_ROOT` | `$GUIALITA_ROOT/data` |
| `GUIALITA_WHISPER_CLI` | `whisper-cli` aus `$PATH` |
| `GUIALITA_VENV` | `$GUIALITA_ROOT/.venv`, sonst `python3` |

`ModelManager` expandiert `${GUIALITA_*}` beim Laden der Konfiguration für
alle Pfadschlüssel und macht sie absolut — nachgelagerte Adapter bleiben
unverändert.

| Datei | absolute Pfade vorher | nachher |
|---|---|---|
| `backend/manager.py` | 1 | 0 |
| `config/models.yaml` | 4 | 0 |
| `scripts/start.sh` | 2 | 0 |
| `scripts/stop.sh` | 2 | 0 |
| `scripts/install_desktop.sh`, `download_models.sh` | 2 | 0 |
| `tests/` (3 Dateien) | 4 | 0 |
| `frontend/index.html` | 1 | 0 |
| **Summe** | **16** | **0** |

**Nicht verändert**: maschinenspezifische Pfade in historischen Phase-Reports
und Baselines. Sie sind forensische Belege.

Nebenbefund und mechanisch repariert: `docs/phase-cuda-vmm-repair.yaml` und
`docs/phase-voice-forensics-v1.yaml` waren kein gültiges YAML (Fließtext
außerhalb eines Schlüssels). Inhalt unverändert, nur als `purpose:`-Block
eingefasst. Sie waren als maschinenlesbar deklariert, aber nicht parsebar.

---

## 5. Validierung

| # | Prüfung | Ergebnis |
|---|---|---|
| 1 | `py_compile` über backend/ scripts/ tests/ | **PASS** |
| 2 | `bash -n` über alle `scripts/*.sh` | **PASS** |
| 3 | YAML-Parsing aller `docs/*.yaml` + `config/*.yaml` | **PASS** (nach Reparatur von 2 Dateien) |
| 4 | Pfadauflösung ohne `.env` (repo-relativ) | **PASS** |
| 5 | Pfadauflösung mit Env-Override | **PASS** |
| 6 | `.env`-Datei wird gelesen, Env hat Vorrang | **PASS** |
| 7 | Modellpfade absolut, keine Platzhalter übrig | **PASS** (6/6 Modelle) |
| 8 | Referenzmaschinen-Pfade per `.env` exakt reproduzierbar | **PASS** |
| 9 | Backend startet (`backend/main.py`) | **PASS** |
| 10 | `GET /health` | **PASS** (HTTP 200, `api: online`) |
| 11 | `GET /models` | **PASS** (6 Modelle, Pfade korrekt aufgelöst) |
| 12 | `tests/test_voice_activation.py` | **PASS** (37/37) |
| 13 | `tests/test_memory_retrieval.py` Unit-Teil | **PASS** (10/10) |
| 14 | `tests/test_memory_graph.py` Unit-Teil | **PASS** (10/10) |
| 15 | API-/Integrationstests | **NOT EXECUTED** |
| 16 | Chat-/Inferenz-Regression | **NOT EXECUTED** |
| 17 | STT-/TTS-/Capture-Regression | **NOT EXECUTED** |
| 18 | GPU-/CUDA-Verifikation | **NOT EXECUTED** |

**Zu 15–18**: Die Validierungsumgebung hat keine Modelldateien, keine GPU,
kein Mikrofon, kein whisper.cpp und keinen Liquid-Audio-Runner. Diese Tests
sind **NOT EXECUTED**, nicht `PASS` und nicht `FAIL`. Alle beobachteten
Testfehler waren `Connection refused` bzw. Folgefehler daraus — keiner ging
auf eine Änderung dieser Phase zurück.

**Vollständige Regression steht aus** und muss auf der Referenzmaschine
gefahren werden:

```bash
cp .env.example .env      # GUIALITA_EXTERNAL_MODEL_ROOT + GUIALITA_WHISPER_CLI setzen
bash scripts/start.sh
python3 tests/test_api.py && python3 tests/test_tts.py && python3 tests/test_voice_activation.py
```

Ohne `.env` findet GUIALITA auf der Referenzmaschine die externen Modelle
nicht — das ist der beabsichtigte Preis der Portabilität und der einzige
Migrationsschritt.

---

## 6. Nicht angefasst

Phase 1C, die Voice→LFM→TTS-Pipeline, Modellarchitektur, whisper.cpp als
STT, Memory-/Graph-Schichten, Ollama, Datenbankinhalte, Modelldateien,
historische Phase-Reports. Keine neuen Features, keine MUSCAL-Schichten.

---

## 7. Verbleibende Risiken

1. **Regression auf der Zielmaschine offen** — höchstes Risiko dieser Phase.
   `.env` muss angelegt werden, sonst fehlen die externen Modelle.
2. **Voice-Latenz-Gate weiter offen** — 48 s stammen aus der Zeit vor dem
   CUDA-Repair; die reale aktuelle Latenz ist unbekannt.
3. **Tests nicht CI-fähig** — Backend, Mikrofon, GPU, Modelle nötig.
   Unverändert durch diese Phase, aber weiterhin gültig.
4. **PROTOTYPEN/** — drei Next.js-Prototypen ohne Bezug zur Python-Pipeline,
   inkl. eines Ordners mit Leerzeichen und Klammern im Namen. Altlast,
   bewusst nicht angefasst.

---

## 8. Empfohlene nächste Phase

**Voice-Latenz-Nachmessung** — das einzige offene Gate.

Ein Sprach-Turn nach dem CUDA-Repair, Zeit pro Stufe (STT / LLM / Memory /
TTS), Ergebnis nach `docs/GUIALITA_STATE.yaml`. Klein, messbar, schließt
`voice_forensics_v1` und liefert erst die Grundlage für jede
Optimierungsentscheidung. Ohne diese Zahl wäre jede weitere Optimierung
Raten.
