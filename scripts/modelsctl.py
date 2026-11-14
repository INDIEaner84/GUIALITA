#!/usr/bin/env python3
"""GUIALITA — Modell-Lifecycle und VRAM-Budget (ADR-002, D3 / P4).

Das Problem, das dieses Skript löst
-----------------------------------
Auf einer GTX 1080 Ti mit 11 GB passen nicht alle konfigurierten Modelle
gleichzeitig. Ein Rollenwechsel ist deshalb nicht kostenlos: wird ein anderes
Modell gebraucht, muss das alte gehen. Wer das als Umschalter denkt, baut eine
Orchestrierung, die bei jedem Schritt Sekunden verliert.

Dieses Skript macht daraus eine Rechenaufgabe:

    status   was konfiguriert und als Datei vorhanden ist (kein Ladezustand)
    health   Runtime und GPU-Zustand aus /health
    budget   was passt in den Speicher — Gewichte + Overhead + Reserve
    plan     was müsste weichen, damit ein Modell geladen werden kann
    switch   Modellwechsel durchführen und **messen**, wie lange er dauert
    load     Alias für switch: lädt ein Modell über den ersten Chat-Turn
    start    delegiert an scripts/start.sh, prüft danach /health
    stop     delegiert an scripts/stop.sh, ohne Ollama anzufassen
    unload   weist auf den fehlenden Entlade-Endpunkt hin und stoppt das Backend

Prozessgrenze (ADR-002 D6)
--------------------------
Es gibt **keine eigene Prozessverwaltung**. ``start`` und ``stop`` rufen
ausschließlich die vorhandenen Shell-Skripte auf und bewerten Exitcode, Log und
``/health``. Ollama bleibt ein SHARED SERVICE: ``stop.sh`` beendet nur
GUIALITA-Prozesse. Ein Lifecycle-Manager, der fremde Prozesse killt, wäre ein
Risiko ohne Gegenwert.

Was es absichtlich nicht tut
----------------------------
* **Nichts, was nicht deklariert ist.** Fehlt eine Modellgröße, gilt sie als
  UNKNOWN und das Urteil lautet "nicht entscheidbar" — nicht "passt schon".
* **Keine erfundenen Entlade-Endpunkte.** Das Backend hat keinen
  ``/models/unload``; ``unload`` sagt das und stoppt das Backend nach
  ausdrücklichem ``--yes``.
* **Kein erfundener Ladezustand.** ``GET /models`` meldet ``available`` =
  „Datei vorhanden", nicht „im VRAM geladen". ``plan`` und ``switch`` nutzen
  deshalb ``--loaded`` oder arbeiten mit einer ausdrücklich als unbekannt
  markierten Annahme. Sie behaupten nie, den VRAM-Inhalt zu kennen.
* **Keine Zahlen ohne Messung.** ``switch`` nimmt die Zeit tatsächlich ab; die
  Zahl aus ``config/model_budget.json`` ist eine Schätzung und als solche
  gekennzeichnet.

Nutzung
-------
    python3 scripts/modelsctl.py status
    python3 scripts/modelsctl.py budget
    python3 scripts/modelsctl.py budget --set granite-8b,lfm-audio-1.5b
    python3 scripts/modelsctl.py plan granite-8b
    python3 scripts/modelsctl.py switch granite-3b
    python3 scripts/modelsctl.py start --yes
    python3 scripts/modelsctl.py stop --yes
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUDGET_FILE = ROOT / "config" / "model_budget.json"

EXIT_OK = 0
EXIT_RISK = 1          # passt nicht / nicht entscheidbar
EXIT_UNAVAILABLE = 2   # Backend oder Werkzeug fehlt


# ----------------------------------------------------------------------------
# Konfiguration
# ----------------------------------------------------------------------------
def load_budget(path: Path = BUDGET_FILE) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def model_size_gb(model_id: str, budget: dict, live_sizes: dict | None = None) -> float | None:
    """Größe eines Modells in GB — live gemessen vor deklariert.

    Reihenfolge: live > deklariert > None (UNKNOWN). None ist ein gültiges
    Ergebnis und wird nie zu 0.
    """
    if live_sizes and live_sizes.get(model_id) is not None:
        return float(live_sizes[model_id])
    entry = (budget.get("models") or {}).get(model_id) or {}
    value = entry.get("weights_gb")
    return float(value) if value is not None else None


def needed_gb(model_ids: list[str], budget: dict,
              live_sizes: dict | None = None) -> tuple[float | None, list[str]]:
    """Summe aus Gewichten + Overhead + Reserve.

    Gibt (bedarf, unbekannte_modelle) zurück. Ist ein Modell UNKNOWN, ist der
    Bedarf insgesamt UNKNOWN — die Teilsumme wird trotzdem mitgeliefert, damit
    man sieht, wie viel fehlt.
    """
    unknown = []
    total = float(budget.get("overhead_gb", 0.0)) + float(budget.get("kv_reserve_gb", 0.0))
    for model_id in model_ids:
        size = model_size_gb(model_id, budget, live_sizes)
        if size is None:
            unknown.append(model_id)
            continue
        total += size
    return (None if unknown else round(total, 2)), unknown


def free_vram_gb(budget: dict) -> tuple[float, str]:
    """Freier VRAM: nvidia-smi, falls vorhanden — sonst deklarierter Wert."""
    if shutil.which("nvidia-smi"):
        try:
            output = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
            if output:
                return round(int(output[0].strip()) / 1024, 2), "nvidia-smi"
        except (ValueError, OSError, subprocess.SubprocessError):
            pass
    return float(budget.get("gpu", {}).get("total_gb", 0.0)), "deklariert (kein nvidia-smi)"


def fits(model_ids: list[str], budget: dict, live_sizes: dict | None = None,
         available_gb: float | None = None) -> dict:
    """Urteil über eine Modellkombination — dreiwertig, nicht zweiwertig."""
    need, unknown = needed_gb(model_ids, budget, live_sizes)
    available, source = (available_gb, "übergeben") if available_gb is not None \
        else free_vram_gb(budget)
    verdict = {
        "models": model_ids,
        "needed_gb": need,
        "unknown": unknown,
        "available_gb": round(available, 2),
        "source": source,
    }
    if unknown:
        verdict["result"] = "unknown"
        verdict["reason"] = (f"Größe unbekannt für {', '.join(unknown)} — "
                             f"nicht entscheidbar")
    elif need <= available:
        verdict["result"] = "fits"
        verdict["headroom_gb"] = round(available - need, 2)
    else:
        verdict["result"] = "too_big"
        verdict["excess_gb"] = round(need - available, 2)
    return verdict


def plan(model_id: str, loaded: list[str], budget: dict,
         live_sizes: dict | None = None,
         available_gb: float | None = None) -> dict:
    """Was müsste entladen werden, damit ``model_id`` passt?

    Entladen wird in der Reihenfolge der zuletzt geladenen Modelle (LIFO) —
    das ist die Reihenfolge, in der ein Cache üblicherweise räumt.
    """
    keep = [m for m in loaded if m == model_id]
    order = [m for m in reversed(loaded) if m != model_id]
    unload: list[str] = []
    while True:
        trial = keep + [m for m in loaded if m not in unload and m != model_id]
        verdict = fits([model_id] + [m for m in trial if m != model_id],
                       budget, live_sizes, available_gb)
        if verdict["result"] in ("fits", "unknown"):
            return {"target": model_id, "unload": unload,
                    "verdict": verdict, "loaded": loaded}
        if not order:
            return {"target": model_id, "unload": unload,
                    "verdict": verdict, "loaded": loaded,
                    "blocked": True}
        unload.append(order.pop(0))


# ----------------------------------------------------------------------------
# Live-Zugriff und Prozessdelegation
# ----------------------------------------------------------------------------
def http_json(url: str, payload: dict | None = None, timeout: float = 60.0):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data,
                                     method="POST" if data else "GET")
    if data:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def live_state(base_url: str) -> dict:
    health = http_json(base_url + "/health")
    models = http_json(base_url + "/models").get("models", [])
    return {
        "health": health,
        "models": models,
        "sizes": {m["id"]: m.get("size_gb") for m in models if m.get("size_gb")},
        "available_ids": [m["id"] for m in models if m.get("available")],
        # /models liefert keinen Ladezustand — bewusst False, nicht geraten.
        "load_state_known": False,
    }


def run_script(name: str, extra: list[str] | None = None,
               timeout: float = 120.0) -> subprocess.CompletedProcess:
    """Ruft ausschließlich ein vorhandenes Skript auf — keine eigene Prozesslogik."""
    path = ROOT / "scripts" / name
    if not path.is_file():
        raise FileNotFoundError(f"Skript fehlt: {path}")
    return subprocess.run(["bash", str(path)] + list(extra or []),
                          cwd=ROOT, capture_output=True, text=True,
                          timeout=timeout)


def print_script_tail(proc: subprocess.CompletedProcess, limit: int = 8) -> None:
    lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    for line in lines[-limit:]:
        print(f"      {line}")
    for line in [line for line in (proc.stderr or "").splitlines() if line.strip()][-3:]:
        print(f"      ! {line}")


def require_yes(args) -> bool:
    if getattr(args, "yes", False):
        return True
    print("  Abgebrochen: dieser Befehl verändert Prozesse. --yes ist Pflicht.")
    print("  Ollama bleibt in jedem Fall unangetastet (SHARED SERVICE).")
    return False


# ----------------------------------------------------------------------------
# Befehle
# ----------------------------------------------------------------------------
def cmd_status(base_url: str) -> int:
    try:
        state = live_state(base_url)
    except Exception as exc:  # noqa: BLE001
        print(f"  Backend nicht erreichbar ({base_url}): {type(exc).__name__}")
        print("  Status ohne Backend ist nicht möglich — es wird nichts geraten.")
        return EXIT_UNAVAILABLE

    runtime = state["health"].get("primary_runtime", {})
    print(f"  Runtime      : {runtime.get('runtime')} — {runtime.get('status')}"
          f"   GPU: {runtime.get('gpu')}")
    print(f"  Default      : {state['health'].get('default_model')}")
    print()
    print(f"  {'ID':<18}{'Name':<20}{'Adapter':<10}{'GB':>7}  Vorhanden")
    print("  " + "-" * 66)
    for model in state["models"]:
        size = f"{model['size_gb']:.2f}" if model.get("size_gb") else "—"
        print(f"  {model['id']:<18}{str(model.get('name'))[:19]:<20}"
              f"{str(model.get('adapter')):<10}{size:>7}  "
              f"{'ja' if model.get('available') else 'NEIN'}")
    print()
    print("  'Vorhanden' = Datei gefunden. Das Backend meldet keinen "
          "VRAM-Ladezustand.")
    return EXIT_OK


def cmd_health(base_url: str) -> int:
    try:
        health = http_json(base_url + "/health")
    except Exception as exc:  # noqa: BLE001
        print(f"  /health nicht erreichbar: {type(exc).__name__}: {exc}")
        return EXIT_UNAVAILABLE
    runtime = health.get("primary_runtime", {})
    print(f"  Runtime : {runtime.get('runtime')} — {runtime.get('status')}")
    print(f"  GPU     : {runtime.get('gpu')}")
    print(f"  Default : {health.get('default_model')}")
    print(f"  Modelle : {len(health.get('models', []))} konfiguriert")
    return EXIT_OK if runtime.get("status") == "online" else EXIT_RISK


def cmd_budget(args, budget: dict) -> int:
    live_sizes = {}
    if args.live:
        try:
            live_sizes = live_state(args.url)["sizes"]
            print(f"  Modellgrößen live vom Backend übernommen "
                  f"({len(live_sizes)} Modelle).")
        except Exception as exc:  # noqa: BLE001
            print(f"  --live nicht möglich ({type(exc).__name__}), "
                  f"nutze deklarierte Werte.")

    available, source = free_vram_gb(budget)
    print(f"  Freier Speicher: {available} GB  (Quelle: {source})")
    print()

    targets = ([m.strip() for m in args.set.split(",") if m.strip()] if args.set
               else list((budget.get("models") or {}).keys()))
    for model_id in targets:
        verdict = fits([model_id], budget, live_sizes)
        size = model_size_gb(model_id, budget, live_sizes)
        mark = {"fits": "passt", "too_big": "ZU GROSS",
                "unknown": "UNBEKANNT"}[verdict["result"]]
        size_text = f"{size:.2f} GB" if size is not None else "—"
        print(f"  {model_id:<20}{size_text:>10}   {mark:<10}"
              f"  Bedarf {verdict['needed_gb'] if verdict['needed_gb'] is not None else '—'} GB")
        if verdict["result"] == "unknown":
            print(f"      {verdict['reason']}")
        if verdict["result"] == "too_big":
            print(f"      über Budget um {verdict['excess_gb']} GB")

    if args.set:
        verdict = fits(targets, budget, live_sizes)
        print()
        print(f"  Kombination {targets}: {verdict['result'].upper()}")
        if verdict.get("headroom_gb") is not None:
            print(f"  Rest: {verdict['headroom_gb']} GB")
        if verdict.get("excess_gb"):
            print(f"  Fehlt: {verdict['excess_gb']} GB")
        return EXIT_OK if verdict["result"] == "fits" else EXIT_RISK

    return EXIT_OK


def cmd_plan(args, budget: dict) -> int:
    live_sizes, loaded = {}, []
    try:
        state = live_state(args.url)
        live_sizes = state["sizes"]
        # available != geladen. Ohne --loaded wird der Ladezustand als
        # unbekannt behandelt und die Annahme ausdrücklich genannt.
        loaded = [m.strip() for m in (getattr(args, "loaded", None) or "").split(",")
                  if m.strip()]
        if not loaded:
            print("  Ladezustand: UNBEKANNT — /models meldet nur Dateiverfügbarkeit.")
            print("  Annahme für diese Budgetrechnung: nichts zusätzlich geladen.")
    except Exception:  # noqa: BLE001
        print("  Backend nicht erreichbar — Plan ohne Live-Größen.")
        print("  Annahme: deklarierte Größen, Ladezustand unbekannt.")

    result = plan(args.model, loaded, budget, live_sizes)
    print(f"  Ziel: {args.model}")
    print(f"  Urteil: {result['verdict']['result']}")
    if result["unload"]:
        print(f"  Müsste weichen: {', '.join(result['unload'])}")
    else:
        print("  Nichts muss weichen.")
    if result.get("blocked"):
        print("  Auch nach Entladen aller anderen Modelle passt es nicht.")
    return EXIT_OK if result["verdict"]["result"] == "fits" else EXIT_RISK


def cmd_switch(args, budget: dict) -> int:
    try:
        state = live_state(args.url)
    except Exception as exc:  # noqa: BLE001
        print(f"  Backend nicht erreichbar: {type(exc).__name__}")
        return EXIT_UNAVAILABLE

    live_sizes = state["sizes"]
    verdict = fits([args.model], budget, live_sizes)
    if verdict["result"] != "fits" and not args.force:
        print(f"  Wechsel abgelehnt: {verdict['result']}"
              f" ({verdict.get('reason') or 'über Budget'})")
        print("  Mit --force trotzdem versuchen (dann ist der Absturz wahrscheinlich).")
        return EXIT_RISK

    loaded = [m.strip() for m in (getattr(args, "loaded", None) or "").split(",")
              if m.strip()]
    if not loaded:
        print("  Ladezustand: UNBEKANNT — /models meldet nur Dateiverfügbarkeit.")
        print("  Der Budgetplan geht daher von keinem zusätzlich geladenen Modell aus.")
    switch_plan = plan(args.model, loaded, budget, live_sizes)
    if switch_plan["unload"]:
        print(f"  Budget-Plan: {', '.join(switch_plan['unload'])} müsste weichen.")

    print(f"  Wechsel auf {args.model} — Messung inklusive Ladezeit …")
    started = time.perf_counter()
    try:
        body = http_json(args.url + "/chat",
                         {"message": "Antworte mit genau einem Wort: bereit",
                          "model": args.model}, timeout=args.timeout)
    except urllib.error.HTTPError as exc:
        print(f"  Wechsel fehlgeschlagen: HTTP {exc.code}")
        return EXIT_RISK
    except Exception as exc:  # noqa: BLE001
        print(f"  Wechsel fehlgeschlagen: {type(exc).__name__}: {exc}")
        return EXIT_RISK
    wall_ms = (time.perf_counter() - started) * 1000

    if isinstance(body, dict) and body.get("status") == "error":
        print(f"  Wechsel fehlgeschlagen: {body.get('error', '?')} — "
              f"{body.get('details', '')}")
        return EXIT_RISK
    reported = body.get("latency_ms") if isinstance(body, dict) else None
    print(f"  Wanduhr bis zur ersten Antwort : {wall_ms:.0f} ms")
    if reported:
        print(f"  davon laut Backend (Inferenz)  : {reported:.0f} ms")
        print(f"  Lade-/Wechselanteil (Differenz): {max(0.0, wall_ms - reported):.0f} ms")
    print()
    print("  Diese Zahl ist die Wechselkosten-Größe aus ADR-002, D3.")
    print("  Sie gehört in jede Planung, die mehrere Rollen mit verschiedenen")
    print("  Modellen kombiniert.")
    return EXIT_OK


def cmd_start(args) -> int:
    if not require_yes(args):
        return EXIT_UNAVAILABLE
    extra = ["--restart"] if getattr(args, "restart", False) else []
    print(f"  Delegiere an scripts/start.sh {' '.join(extra)}".rstrip() + " …")
    try:
        proc = run_script("start.sh", extra, timeout=args.script_timeout)
    except Exception as exc:  # noqa: BLE001
        print(f"  Start nicht möglich: {type(exc).__name__}: {exc}")
        return EXIT_UNAVAILABLE
    print_script_tail(proc)
    if proc.returncode != 0:
        print(f"  start.sh Exitcode {proc.returncode} — kein Erfolg behauptet.")
        return EXIT_UNAVAILABLE
    try:
        health = http_json(args.url + "/health")
    except Exception as exc:  # noqa: BLE001
        print(f"  start.sh meldet Erfolg, aber /health antwortet nicht: "
              f"{type(exc).__name__}")
        return EXIT_UNAVAILABLE
    runtime = health.get("primary_runtime", {})
    print(f"  /health: {runtime.get('runtime')} — {runtime.get('status')}")
    print("  Ollama wurde nur erkannt, nicht verändert (start.sh, Abschnitt 6).")
    if runtime.get("status") != "online":
        print("  /health antwortet, aber die primäre Runtime ist NICHT online —")
        print("  kein Erfolg behauptet.")
        return EXIT_RISK
    return EXIT_OK


def cmd_stop(args) -> int:
    if not require_yes(args):
        return EXIT_UNAVAILABLE
    print("  Delegiere an scripts/stop.sh …")
    try:
        proc = run_script("stop.sh", timeout=args.script_timeout)
    except Exception as exc:  # noqa: BLE001
        print(f"  Stop nicht möglich: {type(exc).__name__}: {exc}")
        return EXIT_UNAVAILABLE
    print_script_tail(proc)
    if proc.returncode != 0:
        print(f"  stop.sh Exitcode {proc.returncode} — kein Erfolg behauptet.")
        return EXIT_UNAVAILABLE
    try:
        http_json(args.url + "/health")
        print("  /health antwortet weiterhin — möglicherweise anderer Prozess.")
        return EXIT_RISK
    except Exception:  # noqa: BLE001
        print("  /health nicht mehr erreichbar.")
    print("  Ollama läuft weiter (SHARED SERVICE, stop.sh ändert es nicht).")
    return EXIT_OK


def cmd_unload(args) -> int:
    print("  Das Backend hat keinen /models/unload-Endpunkt (backend/main.py).")
    print("  Entladen bedeutet hier: GUIALITA-Backend kontrolliert stoppen.")
    print("  Ollama bleibt unangetastet.")
    return cmd_stop(args)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Modell-Lifecycle und VRAM-Budget. Prozesse nur über start.sh/stop.sh.")
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--timeout", type=float, default=300.0,
                        help="Timeout für den Wechsel-Warmup")
    parser.add_argument("--script-timeout", type=float, default=120.0)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Modelle und Verfügbarkeit")
    sub.add_parser("health", help="Runtime-Zustand aus /health")

    budget_parser = sub.add_parser("budget", help="VRAM-Budget prüfen")
    budget_parser.add_argument("--set", metavar="A,B", help="Kombination prüfen")
    budget_parser.add_argument("--live", action="store_true",
                               help="Modellgrößen vom Backend holen")

    plan_parser = sub.add_parser("plan", help="was für ein Modell weichen muss")
    plan_parser.add_argument("model")
    plan_parser.add_argument("--loaded", metavar="A,B",
                             help="tatsächlich geladene Modelle; /models meldet nur Dateiverfügbarkeit")

    for command, help_text in (("switch", "Modell wechseln und messen"),
                               ("load", "Modell über ersten Chat-Turn laden")):
        child = sub.add_parser(command, help=help_text)
        child.add_argument("model")
        child.add_argument("--force", action="store_true",
                           help="trotz Budget-Warnung versuchen")
        child.add_argument("--loaded", metavar="A,B",
                           help="tatsächlich geladene Modelle für den Budgetplan")

    for command in ("start", "stop", "unload"):
        child = sub.add_parser(command, help=f"{command} über die vorhandenen Skripte")
        child.add_argument("--yes", action="store_true",
                           help="bestätigt, dass Prozesse verändert werden dürfen")
        if command == "start":
            child.add_argument("--restart", action="store_true",
                               help="start.sh --restart aufrufen")

    args = parser.parse_args()
    budget = load_budget()

    if args.command == "status":
        return cmd_status(args.url)
    if args.command == "health":
        return cmd_health(args.url)
    if args.command == "budget":
        return cmd_budget(args, budget)
    if args.command == "plan":
        return cmd_plan(args, budget)
    if args.command in ("switch", "load"):
        return cmd_switch(args, budget)
    if args.command == "start":
        return cmd_start(args)
    if args.command == "stop":
        return cmd_stop(args)
    if args.command == "unload":
        return cmd_unload(args)
    return EXIT_UNAVAILABLE


if __name__ == "__main__":
    sys.exit(main())
