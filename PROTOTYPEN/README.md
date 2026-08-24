# PROTOTYPEN — Erkundungen, kein Produktivcode

**Status: NICHT ANGEBUNDEN. NICHT LAUFFÄHIG. NICHT GEPFLEGT.**

Dieses Verzeichnis enthält drei TypeScript/Next.js-Erkundungen aus einer
frühen Projektphase. Sie haben **keine Verbindung** zur produktiven
Python-Runtime von GUIALITA: eigene Konfiguration, eigene Datenbank, eigene
Modellanbindung, eigener Technologiestack.

Diese Datei existiert, weil das Verzeichnis den Eindruck erweckte, GUIALITA
besitze bereits einen Desktop-Agenten mit Bildschirmsteuerung. Das ist nicht
der Fall.

---

## Was hier liegt

| Verzeichnis | Idee | Zustand |
|---|---|---|
| `local-lfm-api-foundation/` | Next.js-Wrapper um lokale LFM-Runtimes | Erkundung, abgelöst durch `backend/` (FastAPI) |
| `local-multimodal-desktop-agent/` | Desktop-Agent: Screenshot, Maus, Tastatur, Vision | Erkundung, nie gegen einen echten Desktop ausgeführt |
| `multimodal-ui-builder-agent (Kopie 1)/` | UI-Builder-Agent | Duplikat („Kopie 1"), ohne erkennbaren Eigenwert |

---

## Warum der Desktop-Agent nicht als Fähigkeit zählt

Belege aus dem Code selbst:

1. **Standardmäßig abgeschaltet** — `config.ts`:
   `controlEnabled: envBool("GUIALITA_CONTROL_ENABLED", false)`,
   mit dem Kommentar *„turn on when xdotool is installed"*.
2. **Vision ist ein Platzhalter** — `vision/engine.ts` liefert im Standardfall
   den Text *„[stub vision] I cannot really see the image"*.
3. **Nicht installiert** — kein `node_modules`, die App wurde nie gebaut.
4. **Die Steuerbefehle sind fehlerhaft** — `desktop/engine.ts` ruft
   `xdotool mouseclick` und `xdotool mousescroll` auf. **Beide Unterbefehle
   existieren in xdotool nicht** (korrekt wären `click` bzw. `click 4/5`).
   Dieser Code kann nie gegen einen echten X-Server gelaufen sein.

Punkt 4 ist der eigentliche Beweis: Es handelt sich um eine Skizze, nicht um
eine deaktivierte Funktion.

---

## Verhältnis zur produktiven Runtime

```text
GUIALITA (produktiv, Python)          PROTOTYPEN/ (Erkundung, TypeScript)
  backend/  FastAPI, Port 8080          eigener Next.js-Server
  data/guialita.db                      data/wrack.sqlite
  config/models.yaml                    src/gui_alita/config.ts
  whisper.cpp · Granite · LFM-Audio     Stub-Provider
        └── keine gemeinsame Schnittstelle, kein Aufruf in beide Richtungen
```

Der maßgebliche Zustand steht in [`docs/GUIALITA_STATE.yaml`](../docs/GUIALITA_STATE.yaml)
unter `capabilities_absent`.

---

## Wenn Desktop-Steuerung gebaut wird

Dann nicht durch Reaktivieren dieses Prototyps. Sinnvoll wäre ein kleiner
Endpunkt in der produktiven Python-Runtime — Screenshot → Vision → **ein**
bestätigter Klick. Voraussetzung ist eine funktionierende Perzeption; ohne
Vision ist Klicken Blindflug.

Beides steht derzeit unter `prohibitions` und erfordert eine ausdrückliche
Freigabe.

---

## Löschen?

Diese Verzeichnisse werden nicht gebaut, nicht getestet und von nichts
importiert. Sie belegen rund 1,2 MB. Ein Löschen wäre vertretbar — die
Historie bleibt in Git erhalten. Bislang unterblieb es bewusst: sie
dokumentieren erwogene Architekturvarianten. Vor dem Entfernen bitte
Rücksprache.
