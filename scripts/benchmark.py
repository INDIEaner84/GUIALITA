#!/usr/bin/env python3
"""GUIALITA — Latenz-Benchmark pro Stufe (STT, LLM, TTS, Turn).

Warum es dieses Skript in dieser Form gibt
------------------------------------------
Die frühere Fassung maß `memory.embed` und optional `GET /health`. Damit war
keine Aussage über den Engpass möglich — und genau der ist die offene Frage
(`voice_forensics_v1`, Warm-Turn ~48 s vor dem CUDA-Repair). Dieses Skript
misst getrennt, was getrennt kostet, und gibt Perzentile statt Mittelwerte aus:
Ein Mittelwert über 5 Läufe verbirgt genau die Ausreißer, die einen
Sprachassistenten unbenutzbar machen.

Quellen der Messwerte
---------------------
* **lokal, deterministisch** — `memory.embed`, ohne Server, ohne Modell.
* **LLM** — `POST /chat`, Wanduhrzeit plus die vom Backend gemeldete
  `latency_ms`.
* **TTS** — `POST /audio/tts`, Wanduhrzeit plus Header `X-TTS-Latency-Ms`.
* **STT / Turn** — aus `/audit/events`: dort schreibt die Sprachschleife
  `transcription_ms`, `chat_ms` und `total_ms` pro Turn. STT lässt sich nur so
  messen, weil sie einen Audiostream braucht; das Skript erzeugt bewusst
  keinen.

Grenzen
-------
Das Skript **startet und stoppt nichts**. Es misst einen laufenden Zustand.
Ein Kaltstart nach Modellwechsel ist eine eigene Größe (ADR-002, D3) und wird
hier nicht versteckt: der erste Aufruf nach einem Wechsel enthält die
Ladezeit.

Nutzung
-------
    python3 scripts/benchmark.py                        # lokal, ohne Server
    python3 scripts/benchmark.py --live                 # gegen localhost:8080
    python3 scripts/benchmark.py --live --reps 5
    python3 scripts/benchmark.py --live --compare granite-3b granite-8b
    python3 scripts/benchmark.py --live --json docs/measurements/bench.json
    python3 scripts/benchmark.py --live --no-tts        # TTS überspringen
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHAT_PROMPT = "Antworte mit genau einem Wort: bereit"
TTS_TEXT = "Bereit."


# ----------------------------------------------------------------------------
# Statistik
# ----------------------------------------------------------------------------
def percentile(values: list[float], q: float) -> float:
    """Perzentil nach Nearest-Rank — bei kleinen Stichproben robuster als
    Interpolation, weil kein Wert erfunden wird, den niemand gemessen hat."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, math.ceil(q * len(ordered)) - 1)
    return ordered[min(index, len(ordered) - 1)]


def stats(values: list[float]) -> dict:
    values = [float(v) for v in values]
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min_ms": round(min(values), 2),
        "median_ms": round(statistics.median(values), 2),
        "p95_ms": round(percentile(values, 0.95), 2),
        "max_ms": round(max(values), 2),
    }


def fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


# ----------------------------------------------------------------------------
# HTTP (nur stdlib, keine Zusatzabhängigkeit)
# ----------------------------------------------------------------------------
def http_get(url: str, timeout: float = 30.0) -> tuple[object, float, dict]:
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read()
        headers = dict(response.headers)
    wall_ms = (time.perf_counter() - started) * 1000
    try:
        return json.loads(body), wall_ms, headers
    except json.JSONDecodeError:
        return body, wall_ms, headers


def http_post(url: str, payload: dict, timeout: float = 300.0) -> tuple[object, float, dict]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        headers = dict(response.headers)
    wall_ms = (time.perf_counter() - started) * 1000
    try:
        return json.loads(body), wall_ms, headers
    except json.JSONDecodeError:
        return body, wall_ms, headers


# ----------------------------------------------------------------------------
# Lokale, deterministische Messungen
# ----------------------------------------------------------------------------
def run_local(reps: int) -> dict:
    from backend.memory.embed import embed

    texts = ["Wie heißt mein Projekt?", "Welche Phasen sind abgeschlossen?",
             "Was war der CUDA-Repair?"]

    embed_ms = []
    for index in range(reps):
        started = time.perf_counter()
        embed(texts[index % len(texts)])
        embed_ms.append((time.perf_counter() - started) * 1000)

    return {"memory.embed": stats(embed_ms)}


# ----------------------------------------------------------------------------
# Live-Messungen
# ----------------------------------------------------------------------------
def measure_chat(base_url: str, model: str | None, reps: int) -> dict:
    """Misst POST /chat. Jeder Lauf bekommt eine eigene Session, damit die
    Konversationshistorie nicht zwischen den Modellen geteilt wird."""
    wall, reported = [], []
    failures = []
    for index in range(reps):
        payload = {"message": CHAT_PROMPT}
        if model:
            payload["model"] = model
        try:
            body, wall_ms, _ = http_post(base_url + "/chat", payload)
        except urllib.error.HTTPError as exc:
            failures.append(f"HTTP {exc.code}")
            continue
        except Exception as exc:  # noqa: BLE001 — Diagnose, kein Kontrollfluss
            failures.append(type(exc).__name__)
            continue
        wall.append(wall_ms)
        if isinstance(body, dict):
            latency = body.get("latency_ms")
            if isinstance(latency, (int, float)):
                reported.append(float(latency))
        # 1 s Abstand: kein Aufwärm-Artefakt des vorherigen Laufs
        if index + 1 < reps:
            time.sleep(1.0)
    return {"wall": stats(wall), "reported": stats(reported), "failures": failures}


def measure_tts(base_url: str, reps: int) -> dict:
    wall, reported = [], []
    failures = []
    for _ in range(reps):
        try:
            _body, wall_ms, headers = http_post(base_url + "/audio/tts",
                                                {"text": TTS_TEXT})
        except urllib.error.HTTPError as exc:
            failures.append(f"HTTP {exc.code}")
            break
        except Exception as exc:  # noqa: BLE001
            failures.append(type(exc).__name__)
            break
        wall.append(wall_ms)
        header = headers.get("X-TTS-Latency-Ms") or headers.get("x-tts-latency-ms")
        if header is not None:
            try:
                reported.append(float(header))
            except ValueError:
                pass
    return {"wall": stats(wall), "reported": stats(reported), "failures": failures}


def measure_turn_stages(base_url: str) -> dict:
    """Liest die Stufenzeiten echter Sprach-Turns aus dem Audit-Log.

    Liefert leere Statistik, wenn seit dem letzten Log-Rotation kein
    Audio-Turn gelaufen ist — das wird ausgewiesen, nicht als 0 ms ausgegeben.
    """
    try:
        body, _wall, _headers = http_get(base_url + "/audit/events?limit=200")
    except Exception:
        return {"available": False, "reason": "audit nicht erreichbar"}
    if not isinstance(body, list):
        return {"available": False, "reason": "unerwartetes Audit-Format"}

    def collect(key: str) -> list[float]:
        return [float(event[key]) for event in body
                if isinstance(event, dict) and isinstance(event.get(key), (int, float))]

    stages = {
        "stt_ms": stats(collect("transcription_ms")),
        "llm_ms": stats(collect("chat_ms")),
        "turn_ms": stats(collect("total_ms")),
    }
    stages["available"] = bool(stages["turn_ms"].get("n"))
    if not stages["available"]:
        stages["reason"] = "keine Audio-Turns im Audit-Log — STT/Turn nicht messbar"
    return stages


def run_live(base_url: str, models: list[str], reps: int, do_tts: bool,
             do_chat: bool, do_turns: bool) -> dict:
    result: dict = {"base_url": base_url}

    health, health_ms, _ = http_get(base_url + "/health")
    result["health"] = {**stats([health_ms])}
    if isinstance(health, dict):
        result["runtime"] = {
            "primary_runtime": health.get("primary_runtime", {}),
            "models": [m.get("name") for m in health.get("models", [])
                       if isinstance(m, dict)],
        }

    if do_chat:
        targets = models or [None]
        result["chat"] = {}
        for model in targets:
            result["chat"][model or "default"] = measure_chat(base_url, model, reps)

    if do_tts:
        try:
            status, _ms, _h = http_get(base_url + "/audio/tts/status")
            available = bool(isinstance(status, dict) and status.get("available"))
        except Exception:
            available = False
        result["tts"] = (measure_tts(base_url, reps) if available
                         else {"available": False,
                               "reason": "TTS-Runtime nicht verfügbar"})

    if do_turns:
        result["turn_stages"] = measure_turn_stages(base_url)

    return result


# ----------------------------------------------------------------------------
# Ausgabe
# ----------------------------------------------------------------------------
def print_local(local: dict) -> None:
    print("\nLokale, deterministische Messungen (ohne Server)")
    print("-" * 70)
    for label, values in local.items():
        if not values.get("n"):
            print(f"  {label:<28} —")
            continue
        print(f"  {label:<28} n={values['n']:<3} "
              f"median={values['median_ms']:>8.1f} ms  "
              f"p95={values['p95_ms']:>8.1f} ms  max={values['max_ms']:>8.1f} ms")


def print_live(live: dict) -> None:
    print(f"\nLive-Messung gegen {live.get('base_url')}")
    print("-" * 70)
    runtime = live.get("runtime") or {}
    print(f"  Modell: {runtime.get('models') or 'unbekannt'}")
    print(f"  GET /health                 median="
          f"{fmt(live.get('health', {}).get('median_ms'))} ms")

    for model, data in (live.get("chat") or {}).items():
        wall = data["wall"]
        reported = data["reported"]
        if not wall.get("n"):
            print(f"  POST /chat [{model}]        nicht messbar"
                  f"  ({', '.join(data['failures'][:2]) or 'kein Ergebnis'})")
            continue
        print(f"  POST /chat [{model}]")
        print(f"      Wanduhr   n={wall['n']:<3} median={wall['median_ms']:>8.1f} ms"
              f"  p95={wall['p95_ms']:>8.1f} ms  max={wall['max_ms']:>8.1f} ms")
        if reported.get("n"):
            print(f"      Backend   n={reported['n']:<3} median="
                  f"{reported['median_ms']:>8.1f} ms  p95={reported['p95_ms']:>8.1f} ms")

    tts = live.get("tts")
    if tts is not None:
        if tts.get("wall", {}).get("n"):
            wall = tts["wall"]
            print(f"  POST /audio/tts             n={wall['n']:<3} "
                  f"median={wall['median_ms']:>8.1f} ms  p95={wall['p95_ms']:>8.1f} ms")
        else:
            print(f"  POST /audio/tts             nicht gemessen"
                  f"  ({tts.get('reason') or ', '.join(tts.get('failures', [])[:2])})")

    stages = live.get("turn_stages")
    if stages is not None:
        if stages.get("available"):
            for label, key in (("STT", "stt_ms"), ("LLM", "llm_ms"), ("Turn", "turn_ms")):
                values = stages[key]
                print(f"  {label:<26} n={values['n']:<3} "
                      f"median={values['median_ms']:>8.1f} ms  "
                      f"p95={values['p95_ms']:>8.1f} ms")
        else:
            print(f"  STT/Turn                    nicht messbar ({stages.get('reason')})")


def print_comparison(live: dict) -> None:
    chat = live.get("chat") or {}
    if len(chat) < 2:
        return
    names = list(chat)
    print("\nVergleich (Median der Wanduhrzeit)")
    print("-" * 70)
    base = chat[names[0]]["wall"].get("median_ms")
    for name in names:
        median = chat[name]["wall"].get("median_ms")
        if median is None or base is None:
            print(f"  {name:<24} nicht messbar")
            continue
        delta = median - base
        print(f"  {name:<24} {median:>9.1f} ms   "
              f"{'+' if delta >= 0 else ''}{delta:.1f} ms")
    print("\n  Hinweis: der erste Aufruf nach einem Modellwechsel enthält die "
          "Ladezeit.\n  Wechselkosten sind eine eigene Größe (ADR-002, D3) und "
          "werden hier nicht\n  herausgerechnet.")


def git_revision() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=ROOT, capture_output=True, text=True,
                              timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# ----------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Latenz-Benchmark pro Stufe. Startet und stoppt nichts.")
    parser.add_argument("--live", action="store_true",
                        help="gegen ein laufendes Backend messen")
    parser.add_argument("--url", default="http://localhost:8080",
                        help="Basis-URL des Backends")
    parser.add_argument("--reps", type=int, default=3,
                        help="Wiederholungen pro Messung (Default: 3)")
    parser.add_argument("--model", action="append", default=[],
                        metavar="NAME", help="Modell für POST /chat (mehrfach möglich)")
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"),
                        help="zwei Modelle vergleichen (impliziert --live)")
    parser.add_argument("--no-tts", action="store_true", help="TTS überspringen")
    parser.add_argument("--no-chat", action="store_true", help="Chat überspringen")
    parser.add_argument("--no-turns", action="store_true",
                        help="Audit-Stufenzeiten überspringen")
    parser.add_argument("--json", metavar="PFAD",
                        help="Ergebnis als JSON schreiben")
    args = parser.parse_args()

    models = list(args.model)
    if args.compare:
        args.live = True
        models = list(args.compare)
    reps = max(1, args.reps)

    print("GUIALITA Benchmark")
    print("=" * 70)
    print(f"  Revision: {git_revision()}   Zeit: "
          f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")

    report: dict = {
        "schema": 1,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "revision": git_revision(),
        "reps": reps,
        "host": os.uname().nodename if hasattr(os, "uname") else "unknown",
        "local": {},
    }

    try:
        report["local"] = run_local(reps)
        print_local(report["local"])
    except Exception as exc:  # noqa: BLE001 — lokal ist optional
        print(f"\nLokale Messung nicht möglich: {type(exc).__name__}: {exc}")

    exit_code = 0
    if args.live:
        try:
            report["live"] = run_live(args.url, models, reps,
                                      not args.no_tts, not args.no_chat,
                                      not args.no_turns)
        except Exception as exc:  # noqa: BLE001
            print(f"\nLive-Messung abgebrochen: {type(exc).__name__}: {exc}")
            print("  Das Backend ist nicht erreichbar. Messung nicht "
                  "durchgeführt —\n  nicht als 0 ms gewertet.")
            exit_code = 2
        else:
            print_live(report["live"])
            print_comparison(report["live"])
    else:
        print("\n  (Kein --live: nur lokale Messungen. Live-Chat wird nicht "
              "automatisch\n   gestartet, weil er ein Modell lädt und "
              "Inferenzzeit kostet.)")

    if args.json:
        path = Path(args.json).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"\n  Report geschrieben: {path}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
