# GUIALITA — Single Source of Truth

## Verbindliche Quelle

Die einzige verbindliche Projektstatusquelle ist:

```text
docs/GUIALITA_STATE.yaml
```

Dort werden Projektstatus, abgeschlossene Milestones, aktuelle Baseline,
Autorisierungen, bekannte Einschränkungen und nächste Schritte maschinenlesbar
geführt.

## Rollen der übrigen Dokumente

| Datei | Rolle | Verbindlich für Status? |
|---|---|---:|
| `docs/GUIALITA_STATE.yaml` | kanonischer aktueller Zustand | **Ja** |
| `docs/GUIALITA_PHASE_STATUS.md` | lesbare Statusansicht | Nein, abgeleitet |
| `docs/HEARTBEAT.md` | aktueller Fortschritt und Milestones | Nein, Verlauf/Ansicht |
| `docs/SESSION_LOG.md` | chronologisches Änderungs- und Prüfprotokoll | Nein, Evidenz |
| `docs/PHASE_*_RESULT.md` | Ergebnisberichte einzelner Phasen | Nein, historische Evidenz |
| Git-Historie | tatsächliche Codeänderungen | Ja für Änderungen |

## Aktueller kanonischer Stand

- Baseline: `GUIALITA-VOICE-ACTIVATION-V1-PASS`
- Text, Sessions, Memory, Graph, STT, TTS und Voice Activation: implementiert
- M4 Testharness: implementiert
- M5 Audit, Benchmark und Session-Export: implementiert
- Vollständige Runtime-Abnahme: blockiert, solange Zielrechner, Modelle und
  Audio-Runtimes nicht verfügbar sind
- Echter Mikrofon-/Lautsprechertest: erforderlich für Hardware-Abnahme
- Vision/Desktop-Control: nicht als kanonische Produktionsfunktion aktiviert

## Änderungsregel

Bei jeder Statusänderung wird zuerst `GUIALITA_STATE.yaml` aktualisiert. Danach
werden, falls nötig, `HEARTBEAT.md` und `SESSION_LOG.md` ergänzt. Keine andere
Datei darf einen abweichenden aktuellen Status als autoritativ behaupten.

## Was nicht als Statusquelle gilt

- Chatnachrichten allein
- alte Phase-Result-Dateien
- Dateien unter `PROTOTYPEN/`
- vorhandene WAV-Dateien
- historische Testergebnisse ohne aktuellen Lauf
