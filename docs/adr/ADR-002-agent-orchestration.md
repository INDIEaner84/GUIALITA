# ADR-002 — Agenten-Orchestrierung (MUSCAL), Rollenmodell und Modell-Lifecycle

**Status**: PROPOSED — Phasenstatus und `prohibitions` unverändert. Die
P3–P6-Werkzeuge sind als CLI/HTTP-Selbsttests umgesetzt (Abschnitt 5a), aber
keine produktive Orchestrierungsschicht. `current.hard_stop` bleibt `true`.
**Datum**: 2026-11-13
**Kontext**: Analysefrage zu Agentensteuerung ohne IDE, MUSCAL-Orchestrierung
und LoRA-Adaptern als Agenten-Identität
**Betrifft**: `future_target` in `docs/GUIALITA_STATE.yaml`, `prohibitions`
**Verhältnis zu ADR-001**: ergänzend, kein Ersatz. ADR-001 legt die
STT-Runtime fest; diese ADR legt fest, **in welcher Reihenfolge** darüber eine
Orchestrierungsschicht entstehen darf — oder besser: entstehen muss.

---

## 0. Warum diese ADR existiert

Anlass war keine Fehlfunktion, sondern eine Frage: Wie gut ist
Agentensteuerung ohne IDE, ist eine IDE obsolet, wie gut orchestriert MUSCAL
Laden/Starten/Wechseln/Trainieren/Benchmark, und hilft ein LoRA-Adapter pro
Agentenrolle?

Das sind Architekturentscheidungen. Sie werden hier festgehalten, bevor Code
entsteht — nicht danach. Dieses Dokument **beantragt** Entscheidungen. Es
genehmigt nichts. Keine Zeile unter `prohibitions` wird durch diese ADR
aufgehoben.

---

## 1. Bestandsaufnahme (Ist-Zustand bei Entwurf, belegt)

Die folgende Tabelle ist die Momentaufnahme **vor P1/P2 und vor den
Werkzeugen aus Abschnitt 5a**. Sie bleibt als Beleg stehen; die heutigen
Zahlen stehen in `docs/GUIALITA_STATE.yaml`.

Die Ausgangsannahme der Frage lautete, MUSCAL betreibe bereits eine
Agenten-Orchestrierung. Das war zum Entwurfszeitpunkt nicht der Fall. Belege:

| Fähigkeit | Erwartung aus der Frage | Beleg im Repo | Befund |
|---|---|---|---|
| Orchestrierung | vorhanden | `GUIALITA_STATE.yaml`, `future_target`: `status: PLANNED`, damals „Nichts davon ist implementiert" | **zum Entwurfszeitpunkt nicht vorhanden** |
| Modelle laden/wechseln | Lifecycle-Manager | `config/models.yaml` enthält nur Pfade + Parameter | **nicht vorhanden** |
| Modelle starten | pro Rolle | `scripts/start.sh` startet Backend + Default-Modell | **teilweise** (ein Modell) |
| Trainieren | Pipeline | kein Trainingscode, kein Korpus, keine Traces | **nicht vorhanden** |
| Benchmark | Modell-/Rollenvergleich | `scripts/benchmark.py` misst `memory.embed` und optional `GET /health` | **minimal** |
| Multi-Agent | parallele Rollen | `prohibitions`: „Multi-Agent" | **ausgeschlossen** |
| Desktop-Steuerung | MUSCAL-App | `PROTOTYPEN/local-multimodal-desktop-agent`: `controlEnabled=false`, Vision = Stub-Text, keine `node_modules`, `xdotool mouseclick` existiert nicht | **nicht lauffähig** |

Zwei Nebenbefunde, die für die Reihenfolge entscheidend sind:

**a) Die Zahl der nicht-CI-fähigen Suiten widerspricht sich in der SSOT.**
Zum Entwurfszeitpunkt sagte `testing.ci_note` „Sieben von neun", `known_risks`
„8 von 9"; die Tabelle in `docs/BASELINES/REGRESSION_CONTRACT.md` belegte
**8 von 9**. Nach P1 waren es 8 von 13, nach den P3–P6-Suiten **8 von 19**.
Die verbindlichen Zahlen stehen heute in der SSOT: **307 Testfunktionen in 19
Suiten**. Abschnitt 5a führt die Korrektur aus.

**b) Der Benchmark misst nicht, was die Frage unterstellt.**
`scripts/benchmark.py` schreibt selbst: „Live chat is intentionally not run
automatically because it loads a model and costs inference time." Es gibt
damit **keine** Messung für Turn-Latenz, Modellwechsel oder Rollenvergleich —
nur Embedding und Health.

Fazit der Bestandsaufnahme: Eine Orchestrierung kann nicht bewertet werden,
weil es sie nicht gibt. Was es gibt, ist eine solide lokale Runtime mit
belastbarem Regressionsvertrag. Genau darauf muss die Orchestrierung aufsetzen.

---

## 2. Entscheidungen

### D1 — Das Eval-Harness kommt vor der Orchestrierung

**Entscheidung**: Vor jedem Lifecycle-, Rollen- oder UI-Code entsteht ein
Harness, der eine feste Aufgabensammlung gegen eine Modell-/Rollen-Konfiguration
laufen lässt und **Qualität, p50/p95-Latenz und Ressourcenverbrauch**
ausgibt.

**Begründung**: Orchestrierung ohne Messung ist Verwaltung von Vermutungen.
Jede spätere Entscheidung — 3B oder 8B, Prompt A oder B, LoRA ja oder nein —
braucht eine Zahl, sonst ist sie eine Meinung. Der Repo-eigene Grundsatz
„Nachweis statt Erlaubnis" (`freeze_policy` v2) gilt hier genauso.

**Konsequenz**: `scripts/benchmark.py` wird erweitert, nicht ersetzt. Es
misst künftig STT, LLM, TTS und Gesamt-Turn getrennt, mit Wiederholungen und
Perzentilen, und kann zwei Konfigurationen vergleichen.

**Nachweis für „erledigt"**: ein Lauf, der zwei Modelle gegen denselben
Aufgabensatz stellt und die Differenz in ms und Score ausgibt.

---

### D2 — Rollen sind Konfiguration, keine Gewichte

**Entscheidung**: Eine Agentenrolle ist ein Datensatz aus
`{Name, Systemprompt, Tool-Allowlist, Modell, Schrittlimit, Timeout,
Eval-Suite}` in einer versionierten YAML-Datei. **LoRA-Adapter werden
ausdrücklich nicht** als Mittel der Rollenidentität eingesetzt.

**Begründung**:

1. **Rollenverhalten entsteht im Harness, nicht im Gewicht.** Ein „Auditor"
   ist ein Auditor, weil er keine Schreibrechte hat und ein festes
   Berichtsschema liefern muss. Das ist in Sekunden änderbar und per Git
   reviewbar; ein LoRA ist keins von beidem.
2. **Datenlage.** Ein belastbarer Rollen-LoRA braucht einige hundert saubere
   Beispiele pro Rolle. Im Repo existieren **null** Trainings-Traces.
3. **Wartung.** Jedes Basis-Modell-Upgrade invalidiert alle Adapter. Ein
   Projekt, für das zum Entwurfszeitpunkt 141 angebliche Tests in neun Suiten
   galten und das heute **307 Testfunktionen in 19 Suiten** hat, sollte sich
   keine zweite Veraltungsachse bauen.
4. **Hardware.** GTX 1080 Ti (Pascal) hat keine brauchbaren Tensor Cores und
   kein schnelles bf16. QLoRA auf 3B ist möglich, aber langsam — und belegt
   die Karte, die für Inferenz gebraucht wird.

**Wo LoRA später zahlen würde** (nicht Teil dieser ADR, nur Abgrenzung):
feste Ausgabeschemata, Fachjargon, Routing/Klassifikation und vor allem
**Destillation** — ein kleines Modell, das die Entscheidungen eines großen
nachahmt, um Latenz zu senken. Das ist ein messbarer Gewinn. „Ich bin der
Planer-Agent" ist keiner.

---

### D3 — Modell-Lifecycle mit explizitem VRAM-Budget, Wechsel als Kostenstelle

**Entscheidung**: Es gibt **einen** Lifecycle-Manager (laden, entladen,
Status, Health) mit einem deklarierten VRAM-Budget. Jeder Modellwechsel wird
als **gemessene Latenz** behandelt und in der Orchestrierung budgetiert, nicht
wegoptimiert.

**Begründung**: Auf 11 GB VRAM passen nicht alle konfigurierten Modelle
gleichzeitig. Wer „wechseln" als kostenlosen Umschalter denkt, baut eine
Orchestrierung, die bei jedem Rollenwechsel Sekunden verliert — bei einem
Sprachassistenten mit 48 s Warm-Turn (vor dem CUDA-Repair gemessen) ist das
der Unterschied zwischen benutzbar und unbenutzbar.

**Konsequenz**: Rollen, die dasselbe Modell nutzen, teilen sich die Instanz.
Ein Rollenwechsel ist nur dann ein Modellwechsel, wenn die YAML es erzwingt.

---

### D4 — MUSCAL beginnt als CLI/HTTP-Schicht, nicht als Desktop-App

**Entscheidung**: Die Orchestrierung wird zuerst als Kommandozeilen- und
HTTP-Schnittstelle gebaut. Eine Desktop-Oberfläche entsteht erst, wenn es
etwas zu bedienen gibt.

**Begründung**: Eine UI über einer nicht existierenden Orchestrierung ist ein
Dashboard ohne Sensoren. Das Repo hat für diese Fehlerklasse bereits einen
Beleg: den Desktop-Prototypen, der aussieht wie eine Fähigkeit und keine ist.
Diese ADR soll nicht den zweiten erzeugen.

**Konsequenz**: `PROTOTYPEN/local-multimodal-desktop-agent/` bleibt, was es
ist — eine dokumentierte erwogene Variante. Es wird nicht reaktiviert.

---

### D5 — Verifikation bleibt lokal; Cloud nur für Code, nie für Inferenz

**Entscheidung**: Code-Formung, Refactoring, Tests und Audit dürfen in einer
Cloud- oder Sandbox-Umgebung stattfinden. **Jede Verifikation, die GPU, Mikrofon,
Lautsprecher oder Latenz betrifft, findet ausschließlich auf der Referenzmaschine
statt.** Cloud-Inferenz bleibt verboten.

**Begründung**: Der Unterschied zwischen einer Cloud-Sandbox und dem lokalen
Rechner ist nicht „Kernel oder kein Kernel" — beide haben einen echten
Linux-Kernel. Der Unterschied ist **Hardwarezugriff und Datenhoheit**. Zum
Entwurfszeitpunkt waren es acht von neun, nach P1 acht von dreizehn und heute
acht von neunzehn Suiten, die Backend, Modelle, GPU, Mikrofon oder
`espeak-ng` brauchen (Abschnitt 1a). Keine Cloud-Sandbox kann das erbringen.
Umgekehrt ist ein
Cloud-Agent für das Umschreiben von `retrieval.py` oder das Reparieren einer
CI-Datei vollkommen ausreichend.

**Konsequenz**: Die Arbeitsteilung wird explizit dokumentiert, damit niemand
einen grünen Lauf in der Sandbox für eine Hardware-Abnahme hält.

---

### D6 — Orchestrierung ruft Prozesse auf, sie importiert sie nicht

**Entscheidung**: MUSCAL startet und beobachtet GUIALITA-Runtimes als
Prozesse über definierte Schnittstellen (HTTP, Exitcode, Log). Es gibt keinen
gemeinsamen Python-Prozess, in dem Orchestrierung und Modell-Runtime leben.

**Begründung**: Der CUDA-VMM-Crash (`docs/PHASE_CUDA_VMM_REPAIR_RESULT.md`)
zeigt, wie teuer ein instabiler GPU-Prozess ist. Prozessisolation macht einen
Absturz zu einem Neustart statt zu einem Ausfall. Außerdem bleibt die
bestehende Runtime unangetastet — die Orchestrierung kann scheitern, ohne
`POST /chat` zu brechen (`CHAT_REGRESSION`).

---

### D7 — Die SSOT wird vor Orchestrierung zahlenmäßig konsolidiert

**Entscheidung**: Der Widerspruch aus Abschnitt 1a (7 vs. 8 Suiten) wird
bereinigt, bevor Orchestrierungs-Code entsteht. Zusätzlich wird geprüft, ob
weitere Kennzahlen in `GUIALITA_STATE.yaml` gegen die Realität laufen.

**Begründung**: Eine Orchestrierung, die auf einer Statusquelle aufsetzt, die
sich selbst widerspricht, orchestriert den Widerspruch mit. Der Repo-Anspruch
lautet „DIES IST DIE EINZIGE QUELLE DER WAHRHEIT FÜR PHASENSTATUS" — dieser
Anspruch ist nur so viel wert wie die Zahlen darin.

**Nachweis für „erledigt"**: ein Lauf von `scripts/run_all_tests.py --list`,
dessen Suite-/Testzahlen mit der SSOT übereinstimmen.

---

## 3. VRAM-Budget (Schätzung — ausdrücklich keine Messung)

| Modell | Quantisierung | Größe (belegt) | Quelle |
|---|---|---|---|
| granite-4.1-3b | Q4_K_M | 2,1 GB | `README.md`, `docs/PHASE_0_BASELINE.md` |
| granite-4.1-8b | Q4_K_M | 5,35 GB | `docs/PHASE_0_BASELINE.md` |
| LFM2.5-8B-A1B | Q4_K_M | 5,16 GB | `docs/PHASE_0_BASELINE.md` |
| LFM2.5-Audio-1.5B | Q4_0 | UNKNOWN | nicht im Repo dokumentiert |
| LFM2.5-VL-3B | Q4_K_M | UNKNOWN | nicht im Repo dokumentiert |

Zuzüglich KV-Cache bei `n_ctx: 4096` und CUDA-Kontext-Overhead. Die
Konsequenz ist unabhängig von den beiden UNKNOWN-Werten:

- **3B + Audio** → passt komfortabel.
- **8B + Audio** → passt, aber mit wenig Reserve.
- **8B + Vision + Audio** → passt nach dieser Schätzung **nicht**.
- Zwei große Modelle gleichzeitig → **ausgeschlossen**.

Damit ist D3 keine Vorsichtsmaßnahme, sondern eine Rechenaufgabe. Die
tatsächlichen Werte sind zu messen, nicht zu schätzen; diese Tabelle ist eine
Planungsgrundlage und wird nach der ersten Messung ersetzt.

---

## 4. Rollenmodell (Zielbild; Implementierung siehe 5a)

```yaml
# config/roles.yaml — Zielbild
roles:
  router:
    model: granite-3b
    prompt: "klassifiziere die Anfrage, antworte nur mit dem Label"
    tools: []
    output_schema: label
    timeout_ms: 3000
    eval: evals/router.yaml

  planner:
    model: granite-3b
    prompt: "zerlege die Aufgabe in prüfbare Schritte"
    tools: [read_file, list_dir]
    output_schema: plan
    timeout_ms: 20000
    eval: evals/planner.yaml

  coder:
    model: granite-8b
    prompt: "ändere Code minimal-invasiv, erkläre die Differenz"
    tools: [read_file, write_file, run_tests]
    output_schema: diff
    timeout_ms: 120000
    eval: evals/coder.yaml

  auditor:
    model: granite-3b
    prompt: "prüfe gegen den Regression Contract, ändere nichts"
    tools: [read_file, run_tests]      # bewusst ohne write_file
    output_schema: report
    timeout_ms: 120000
    eval: evals/auditor.yaml
```

Zwei Eigenschaften sind wesentlich und beide sind **nicht** Modellsache:
`auditor` hat kein Schreibrecht, und jede Rolle hat eine eigene Eval-Suite.
Wer eine Rolle ändern will, ändert eine Zeile YAML und läuft ihre Suite.

**Umsetzung:** `config/roles.json` ist die maschinelle Quelle,
`config/roles.yaml` die von `scripts/build_roles.py` generierte, ADR-konforme
YAML-Ansicht. Die Eval-Suiten liegen unter `evals/roles/<rolle>.json`; das
Gesamtset `evals/golden.json` wird aus ihnen erzeugt. JSON zusätzlich zu YAML
ist eine bewusste Abweichung vom Formatvorschlag oben: alle Werkzeuge bleiben
damit ohne PyYAML in einer nackten CI-Umgebung prüfbar.

---

## 5. Umsetzungsreihenfolge

„Freigabe" bezieht sich auf `prohibitions` in `docs/GUIALITA_STATE.yaml`.

| P | Vorhaben | Nachweis (Definition of Done) | Freigabe nötig | Hängt ab von |
|---|---|---|---|---|
| **P0** | Voice-Latenz nachmessen (`voice_forensics_v1` schließen) | `docs/measurements/voice-turn-<ts>.yaml` aus `scripts/measure_voice_turn.py --record --turns 3` | nein (bereits empfohlen) | — |
| **P1** | SSOT-Zahlen konsolidieren (D7) | Suite-/Testzahlen stimmen mit `run_all_tests.py --list` überein | nein | — |
| **P2** | Benchmark erweitern: STT/LLM/TTS/Turn getrennt, p50/p95, `--compare` (D1) | Vergleichslauf zweier Modelle mit Differenzausgabe | nein | P0 |
| **P3** | Eval-Harness mit festem Aufgabensatz + Golden Set (D1) | reproduzierbarer Score pro Konfiguration | ja (neue Schicht) | P2 |
| **P4** | Lifecycle-Manager mit VRAM-Budget + Wechselmessung (D3, D6) | `start`/`stop`/`switch`/`status` über CLI, Wechselzeit gemessen | ja | P3 |
| **P5** | Rollen-Registry als YAML + Rollen-Evals (D2) | zwei Rollen, zwei Suiten, ein Wechsel ohne Modellwechsel | ja | P4 |
| **P6** | MUSCAL-CLI/HTTP als Aggregationsschicht (D4) | eine Aufgabe läuft Router → Planner → Coder → Auditor mit Audit-Log | ja | P5 |
| — | LoRA-Training | **zurückgestellt** bis ≥ 200 gelabelte Traces existieren | ja (neue ADR) | P6 |

Die Reihenfolge ist nicht beliebig: P2 und P3 liefern die Zahlen, ohne die P5
nicht bewertbar wäre, und P4 liefert die Wechselkosten, ohne die P6 nur eine
Kette von Ladezeiten wäre.

---

## 5a. Umsetzungsstand (Änderungshistorie, keine Statusangabe)

Der Phasenstatus steht ausschließlich in `docs/GUIALITA_STATE.yaml`. Hier nur,
was seit dem Entwurf tatsächlich am Code passiert ist.
**P3–P6 als CLI/HTTP-Werkzeuge umgesetzt** heißt ausdrücklich nicht, dass eine
produktive Orchestrierungsschicht, ein Desktop-Adapter oder parallele Agenten
freigegeben wären. `current.hard_stop`, `next_authorized_phase: NONE` und
`prohibitions` sind unverändert.

- **P1 umgesetzt (2026-11-13).** `count_test_functions` in
  `scripts/run_all_tests.py` nutzt `ast` statt der Regex `\s+def test`. Damit
  wurden zwei Fehler sichtbar: `test_process_audio.py` zählte 5 statt 14,
  `test_capture.py` 0 statt 6. Zugleich standen `test_audit.py`,
  `test_chat_service.py` und `test_audio_contract.py` in der SSOT, aber nicht
  in der Runner-Liste — sie liefen nie. Alle drei sind jetzt enthalten.
  Neuer Befehl `--check-state` gleicht Runner und SSOT ab; ein CI-Workflow
  (`.github/workflows/state-consistency.yml`) führt ihn aus.
- **P2 umgesetzt (2026-11-13).** `scripts/benchmark.py` misst getrennt:
  `memory.embed` lokal, `POST /chat` (Wanduhr + Backend-`latency_ms`),
  `POST /audio/tts` und die Stufenzeiten aus `/audit/events`
  (`transcription_ms`, `chat_ms`, `total_ms`). Ausgabe mit n, Median, p95, max;
  `--compare A B` für Modellvergleich; `--json` für Reports. Fehlende Messungen
  erscheinen als `—`, nicht als 0 ms. `tests/test_benchmark.py` (10 Tests)
  sichert die Rechenwege ab.
- **P3 umgesetzt (2026-11-13).** `scripts/eval.py` mit Golden Set,
  `--dry-run`, `--live --model`, `--compare`, p50/p95 und einem
  `resource_snapshot`, das fehlendes `nvidia-smi` als „nicht gemessen"
  ausweist. `evals/roles/*.json` sind die Quelle, `evals/golden.json` ist
  generiert (`scripts/build_golden.py --check`). 19 Aufgaben, 10 negative
  Kontrollen; `tests/test_eval.py` mit 33 Tests.
- **P4 umgesetzt als CLI-Werkzeug (2026-11-13).** `scripts/modelsctl.py`
  liefert `budget`, `status`, `health`, `plan`, `switch`, `load`, `start`,
  `stop` und `unload`. `start`/`stop` delegieren ausschließlich an
  `scripts/start.sh` / `stop.sh` (D6) und fassen Ollama nicht an. Das
  VRAM-Urteil ist dreiwertig: `fits`, `too_big`, `unknown`. `switch` misst die
  Wanduhr bis zur ersten Antwort — **auf der Referenzmaschine**; in der
  Sandbox existiert diese Messung nicht. `tests/test_modelsctl.py` mit 25 Tests.
- **P5 umgesetzt (2026-11-13).** `config/roles.json` plus generiertes
  `config/roles.yaml`, vier Rollen, vier Rollen-Evals. `scripts/roles.py`
  erzwingt u. a. „Auditor schreibt nicht“, „mutierendes Tool braucht
  Freigabe“ und prüft den YAML-Mirror. `roles.py switch router planner`
  weist den Wechsel **ohne Modellwechsel** nach (D3). `tests/test_roles.py`
  mit 27 Tests.
- **P6 umgesetzt (2026-11-13).** `scripts/muscal.py` führt eine sequenzielle
  Kette `router → planner → [coder] → auditor` mit Schema-Prüfung, Audit-Log,
  STOP-Datei, Schrittgrenze und Staging-Guard aus — als CLI (`run`) **und**
  HTTP (`serve`: `/health`, `/pipelines`, `/guard`, `POST /run`). Kein
  Desktop, kein WebSocket, keine parallelen Agenten. `tests/test_muscal.py`
  (26) und `tests/test_muscal_http.py` (14).
- **Konsistenz nachgezogen (2026-11-13).** `scripts/check_docs.py` prüft die
  aktuellen Zahlen, Grenzen und generierten Artefakte;
  `tests/test_doc_consistency.py` (5). Runner und SSOT melden **307
  Testfunktionen in 19 Suiten**.

- **Live-Contract geprüft (2026-11-13).** `scripts/contract_check.py` startet
  ein Fake-Backend mit den echten `ChatRequest`/`ChatResponse`-Feldern aus
  `backend/models/schemas.py` sowie `/health` und `/models` nach
  `backend/manager.py`. Damit sind Request-Aufbau, Response-Parsing,
  Fehlerantworten, `--model`, Budgetplan und gemessene `switch`-Wanduhr für
  `eval.py`, `modelsctl.py` und `muscal.py` belegt. **Kein** Inferenz-, VRAM-
  oder Latenznachweis: die Antwortwerte des Fake-Backends sind synthetisch.

**Gemessen in der Sandbox:** `eval.py --dry-run` (19/19 Urteile wie erwartet),
`eval.py --dry-run --all-suites` (4/4), `build_golden.py --check`,
`build_roles.py --check`, `roles.py validate --check-mirror`,
`check_docs.py`, `run_all_tests.py --check-state` (keine Abweichung) und der
vollständige Runner (7 PASS, 12 NOT EXECUTED, 0 FAIL).

**Nicht gemessen / offen:** **P0** — Voice-Latenz-Nachmessung auf der
Referenzmaschine. Ebenso offen sind `eval.py --live` und `--compare`,
`modelsctl.py switch/start/stop` mit echter Runtime, `muscal.py --live` bzw.
HTTP ohne `dry_run`, echte VRAM-Belegung und jede Latenzangabe mit GPU. Ein
grüner Sandbox-Lauf ist keine Hardware-Abnahme (D5).

Nebenbefund aus P1: `scripts/run_all_tests.py` klassifiziert
In-process-Suiten jetzt über die Fähigkeit `deps` (importierbar: pydantic,
fastapi). Vorher erschienen sie in einer nackten Umgebung als FAIL
(ImportError), obwohl nichts kaputt war.

## 6. Nicht Gegenstand dieser ADR

Unverändert untersagt bleiben, bis eine eigene ADR sie einzeln öffnet:

- Vision / Perzeption (`capabilities_absent.vision`)
- Desktop- und Browser-Steuerung (`capabilities_absent.desktop_control`)
- WebSocket / Streaming / Full-Duplex
- paralleler Multi-Agent-Betrieb
- jede Cloud-Inferenz für STT, LLM oder TTS
- MUSCAL-Adapter als produktive Schicht

Diese ADR beschreibt eine Reihenfolge, keine Freigabe.

---

## 7. Verworfene Alternativen

| Alternative | Grund der Ablehnung |
|---|---|
| MUSCAL zuerst als Desktop-App mit vielen Schaltflächen | UI ohne Orchestrierung ist ein Dashboard ohne Sensoren; erzeugt denselben Effekt wie der nie gelaufene Desktop-Prototyp |
| LoRA pro Rolle als Identitätsmerkmal | löst ein Prompt-/Rechteproblem auf der Gewichtsebene; keine Daten, keine Evaluierbarkeit, hohe Wartungslast |
| Multi-Agent parallel als Startpunkt | ohne Eval-Harness nicht bewertbar; VRAM-Budget verbietet mehrere große Modelle gleichzeitig |
| Benchmark weiter nur auf `memory.embed` | misst nicht den Engpass; die Frage betrifft Turn-Latenz und Modellvergleich |
| Orchestrierung im selben Prozess wie die Runtime | ein GPU-Absturz würde `POST /chat` mitnehmen und `CHAT_REGRESSION` brechen |
| Cloud-Inferenz für die Sprachschleife | widerspricht dem Projektgrundsatz und dem Zweck der lokalen Runtime |

---

## 8. Revisionsauslöser

Diese ADR wird neu bewertet, wenn:

- die Voice-Latenz nach der Nachmessung (P0) deutlich unter dem bisherigen
  Warm-Turn von 48 s liegt — dann wird Orchestrierung praktisch nutzbar,
- eine zweite GPU oder ≥ 24 GB VRAM verfügbar ist — dann entfällt die
  harte Ausschlusswirkung des VRAM-Budgets in D3,
- ≥ 200 gelabelte Traces vorliegen — dann wird D2 (LoRA) als eigene ADR
  erneut geprüft,
- llama-cpp-python oder `llama-server` ein stabiles Multi-LoRA-Serving mit
  per-Request-Auswahl bieten — dann sinkt der Preis für D2,
- eine stabile, lokal ausführbare Vision-Runtime existiert — dann wird
  Desktop-Control als eigene ADR mit Sicherheitskonzept bewertbar.

---

## 9. Belege

- `docs/GUIALITA_STATE.yaml` — `future_target` (PLANNED), `prohibitions`,
  `testing` (307 Testfunktionen / 19 Suiten / `ci_capable: false`),
  `known_risks`, `capabilities_absent`
- `docs/BASELINES/REGRESSION_CONTRACT.md` — Voraussetzungstabelle der Suiten
  (Auflösung des 7-vs-8-Widerspruchs)
- `scripts/benchmark.py` — Stufenmessung, p50/p95, `--compare`
- `scripts/measure_voice_turn.py` — Werkzeug für P0
- `PROTOTYPEN/README.md` — Nachweis, dass der Desktop-Prototyp keine
  Fähigkeit ist
- `docs/adr/ADR-001-stt-whisper-cpp.md` — Runtimes und Latenzposten
- `docs/PHASE_CUDA_VMM_REPAIR_RESULT.md` — Begründung für Prozessisolation
- `config/models.yaml` — konfigurierte Modelle und Parameter
- `docs/PHASE_0_BASELINE.md` — Modellgrößen
