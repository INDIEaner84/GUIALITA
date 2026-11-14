#!/usr/bin/env python3
"""GUIALITA — Live-Contract-Selbsttest gegen das echte HTTP-Schema.

Warum dieses Skript existiert
-----------------------------
Die Live-Pfade von ``eval.py``, ``modelsctl.py`` und ``muscal.py`` konnten in
der Sandbox nicht gegen ein echtes Backend laufen: kein Modell, keine GPU, kein
Server. „Implementiert" hieß dort bisher nur „der Code kompiliert". Das ist zu
wenig, wenn drei Clients dieselbe HTTP-Schnittstelle unterschiedlich lesen.

Dieses Skript startet deshalb ein **Fake-Backend auf 127.0.0.1:0**, das exakt
die Verträge aus ``backend/models/schemas.py`` und ``backend/manager.py``
liefert:

* ``GET /health`` → ``api``, ``default_model``, ``primary_runtime``, ``models``
* ``GET /models`` → ``{"models": [{id, name, adapter, path, available, size_gb}]}``
* ``POST /chat`` → ``ChatRequest`` (``message``, optional ``model``/``session_id``)
  und ``ChatResponse`` (``status``, ``response``, ``model``, ``latency_ms``, …)
  bzw. ``ErrorResponse`` bei unbekanntem Modell / leerem Text.

Geprüft werden Request-Aufbau, Response-Parsing, Fehlerantworten,
Modell-Override, Budgetplan und die gemessene Wechselzeit. Alles ohne
Installation, ohne Backend-Prozess, ohne Hardware.

Was es **nicht** beweist
------------------------
Keine Inferenzqualität, keine echte Ladezeit, keine VRAM-Belegung. Das Fake-
Backend antwortet mit konstanten Zahlen; ``latency_ms`` ist absichtlich
synthetisch. Die Hardware-Abnahme (P0, `--live`, `switch`) bleibt offen.

Nutzung
-------
    python3 scripts/contract_check.py
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import eval as evalmod  # noqa: E402
import modelsctl  # noqa: E402
import muscal  # noqa: E402

MODEL_ROWS = [
    {"id": "granite-3b", "name": "granite-4.1-3b", "adapter": "llamacpp",
     "path": "/fake/granite-3b.gguf", "available": True, "size_gb": 2.1},
    {"id": "granite-8b", "name": "granite-4.1-8b", "adapter": "llamacpp",
     "path": "/fake/granite-8b.gguf", "available": True, "size_gb": 5.35},
    {"id": "lfm-vision-3b", "name": "LFM2.5-VL-3B", "adapter": "llamacpp",
     "path": "/fake/vision.gguf", "available": False, "size_gb": None},
]
KNOWN_IDS = {row["id"] for row in MODEL_ROWS}


def chat_reply(message: str, model: str) -> dict:
    if "FORCE_ERROR" in message:
        return {"status": "error", "error": "contract_test",
                "model": model, "runtime": "api",
                "details": "absichtliche Fehlerantwort des Fake-Backends"}
    if "genau einem Wort" in message:
        text = "bereit"
    elif "klassifizierst" in message:
        text = "chat"
    else:
        text = "Antwort des Fake-Backends"
    return {
        "status": "success",
        "response": text,
        "model": model,
        "latency_ms": 12.5,
        "runtime": "llamacpp",
        "session_id": "fake-session",
        "message_id": "fake-message",
        "history_used": 0,
        "history_limit": 0,
        "retrieval": None,
    }


class FakeBackendHandler(BaseHTTPRequestHandler):
    """Antwortet wie `backend/main.py`, ohne FastAPI zu importieren."""

    server_version = "GUIALITA-ContractFake/1.0"
    requests: list[dict] = []

    def log_message(self, fmt, *args):
        return

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _health(self) -> dict:
        return {
            "api": "online",
            "default_model": "granite-3b",
            "primary_runtime": {"runtime": "llama-cpp-python",
                                "status": "online", "gpu": True},
            "secondary_runtime": {"status": "online", "runtime": "ollama"},
            "models": MODEL_ROWS,
        }

    def do_GET(self):  # noqa: N802 — http.server vorgeschrieben
        path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        if path == "/health":
            self._send(200, self._health())
        elif path == "/models":
            self._send(200, {"models": MODEL_ROWS})
        else:
            self._send(404, {"status": "error", "error": "not_found",
                             "details": path})

    def do_POST(self):  # noqa: N802 — http.server vorgeschrieben
        if urllib.parse.urlparse(self.path).path != "/chat":
            self._send(404, {"status": "error", "error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (ValueError, UnicodeDecodeError):
            self._send(400, {"status": "error", "error": "invalid_json"})
            return
        if not isinstance(payload, dict) or not str(payload.get("message", "")).strip():
            self._send(400, {"status": "error", "error": "empty_message",
                             "details": "message darf nicht leer sein",
                             "runtime": "api"})
            return
        model = payload.get("model") or "granite-3b"
        if model not in KNOWN_IDS:
            self._send(404, {"status": "error", "error": "unknown_model",
                             "model": model, "runtime": "api",
                             "details": "Verfuegbare Modelle: " + ", ".join(sorted(KNOWN_IDS))})
            return
        FakeBackendHandler.requests.append(dict(payload))
        self._send(200, chat_reply(str(payload["message"]), model))


class FakeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_fake_backend() -> tuple[FakeHTTPServer, str, threading.Thread]:
    server = FakeHTTPServer(("127.0.0.1", 0), FakeBackendHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}", thread


def quiet(callable_, *args, **kwargs):
    """Führt einen CLI-Befehl aus und hält dessen Ausgabe aus dem Report heraus."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = callable_(*args, **kwargs)
    return result, buffer.getvalue()


def run_checks() -> list[str]:
    problems: list[str] = []
    FakeBackendHandler.requests.clear()
    server, base, thread = start_fake_backend()
    roles = muscal.load_roles()["roles"]
    budget = modelsctl.load_budget()

    try:
        # 1) ChatRequest: eval.py sendet message + Rollenprompt + model.
        task = {"id": "contract-router", "role": "router", "prompt": "Hallo",
                "expect": {"equals": "chat"},
                "stub": {"response": "chat", "outcome": "pass"}}
        backend = evalmod.LiveBackend(base, roles, timeout=5)
        try:
            response, latency = backend.ask(task)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"eval.LiveBackend.ask: {type(exc).__name__}: {exc}")
        else:
            if response != "chat":
                problems.append(f"eval.LiveBackend: response={response!r}, erwartet 'chat'")
            if latency <= 0:
                problems.append("eval.LiveBackend: Latenz wurde nicht gemessen")
            sent = FakeBackendHandler.requests[-1] if FakeBackendHandler.requests else {}
            if sent.get("model") != "granite-3b":
                problems.append(f"eval.LiveBackend: model fehlt/falsch: {sent.get('model')}")
            if "klassifizierst" not in str(sent.get("message", "")):
                problems.append("eval.LiveBackend: Rollenprompt wurde nicht vorangestellt")

        # 2) --model muss das Rollenmodell überschreiben.
        override = evalmod.LiveBackend(base, roles, timeout=5,
                                       model_override="granite-8b")
        try:
            override.ask(task)
            sent = FakeBackendHandler.requests[-1]
            if sent.get("model") != "granite-8b":
                problems.append(f"--model greift nicht: {sent.get('model')}")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"eval.LiveBackend --model: {type(exc).__name__}: {exc}")

        # 3) Der vollständige Live-Lauf muss dieselbe Aufgabe als PASS werten.
        report = evalmod.run_live([task], backend)
        if report["results"][0]["graded"] != "pass":
            problems.append("eval.run_live: Aufgabe gegen Fake-Backend nicht PASS")

        # 4) ErrorResponse darf nicht als leere Antwort durchgehen.
        try:
            evalmod.LiveBackend(base, roles, timeout=5).ask(
                {"id": "err", "role": "router", "prompt": "FORCE_ERROR",
                 "expect": {}, "stub": {"response": "", "outcome": "fail"}})
            problems.append("eval.LiveBackend: ErrorResponse wurde nicht erkannt")
        except RuntimeError:
            pass  # erwartet
        except Exception as exc:  # noqa: BLE001
            problems.append(f"eval.LiveBackend: falscher Fehlertyp {type(exc).__name__}")

        # 5) muscal.LiveBackend: Request und Response.
        try:
            text, ms = muscal.LiveBackend(base, timeout=5).ask(
                "router", "Du klassifizierst eine Anfrage. Aufgabe: Hallo", roles["router"])
            if not text or ms <= 0:
                problems.append("muscal.LiveBackend: leere Antwort oder keine Latenz")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"muscal.LiveBackend.ask: {type(exc).__name__}: {exc}")

        # 6) muscal-Kette gegen das Fake-Backend (ein Schritt, Label 'chat').
        try:
            result = muscal.run_pipeline("Hallo", ["router"],
                                         muscal.LiveBackend(base, timeout=5),
                                         roles, False, 5,
                                         ROOT / "data" / "muscal")
            if result["status"] != "ok":
                problems.append(f"muscal.run_pipeline: {result['status']}")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"muscal.run_pipeline: {type(exc).__name__}: {exc}")

        # 7) status / health gegen /models und /health.
        for name, fn in (("status", lambda: modelsctl.cmd_status(base)),
                         ("health", lambda: modelsctl.cmd_health(base))):
            code, _ = quiet(fn)
            if code != 0:
                problems.append(f"modelsctl {name}: Exitcode {code}")

        # 8) plan mit explizit genanntem Ladezustand.
        plan_args = SimpleNamespace(url=base, model="granite-8b",
                                    loaded="granite-3b")
        code, _ = quiet(modelsctl.cmd_plan, plan_args, budget)
        if code != 0:
            problems.append(f"modelsctl plan: Exitcode {code}")

        # 9) switch misst die Wanduhr und liest latency_ms.
        switch_args = SimpleNamespace(url=base, model="granite-8b",
                                      force=False, timeout=5.0, loaded=None)
        code, output = quiet(modelsctl.cmd_switch, switch_args, budget)
        if code != 0:
            problems.append(f"modelsctl switch: Exitcode {code}")
        if "Wanduhr bis zur ersten Antwort" not in output:
            problems.append("modelsctl switch: keine gemessene Wanduhr im Report")
        if "12 ms" not in output and "12.5 ms" not in output:
            problems.append("modelsctl switch: latency_ms aus ChatResponse nicht gelesen")

        # 10) start darf bei offline-Runtime keinen Erfolg behaupten.
        offline = dict(modelsctl.http_json(base + "/health"))
        offline["primary_runtime"] = {"runtime": "llama-cpp-python",
                                      "status": "offline", "gpu": False}
        start_args = SimpleNamespace(yes=True, restart=False, url=base,
                                     script_timeout=5.0)
        proc = SimpleNamespace(returncode=0, stdout="[GUIALITA] fertig\n", stderr="")
        with mock.patch.object(modelsctl, "run_script", return_value=proc), \
             mock.patch.object(modelsctl, "http_json", return_value=offline):
            code, output = quiet(modelsctl.cmd_start, start_args)
        if code == 0:
            problems.append("modelsctl start: behauptet Erfolg trotz offline-Runtime")

        # 11) /chat mit unbekanntem Modell muss 404 liefern (Client sieht HTTPError).
        try:
            bad = evalmod.LiveBackend(base, {}, timeout=5,
                                      model_override="gibtsnicht")
            bad.ask({"id": "bad", "role": "router", "prompt": "x"})
            problems.append("Fake-Backend: unbekanntes Modell nicht abgelehnt")
        except Exception as exc:  # noqa: BLE001
            if "HTTPError" not in type(exc).__name__ and "404" not in str(exc):
                problems.append(f"unbekanntes Modell: unerwarteter Fehler {type(exc).__name__}")

    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    return problems


def main() -> int:
    problems = run_checks()
    print()
    print("=" * 78)
    print("  Live-Contract-Selbsttest (Fake-Backend, echtes Schema)")
    print("=" * 78)
    print(f"  Geprüft: ChatRequest/ChatResponse, /health, /models, /chat")
    print(f"  Clients: eval.py, modelsctl.py, muscal.py")
    print(f"  Fake-Modelle: {', '.join(sorted(KNOWN_IDS))}")
    if problems:
        for problem in problems:
            print(f"  FEHLER  {problem}")
        print(f"\n  {len(problems)} Problem(e).")
        return 1
    print("\n  OK — alle Live-Clients lesen und schreiben das echte HTTP-Schema.")
    print("  Kein Modell, keine GPU, keine Inferenz: dies ist ein Vertragsnachweis,")
    print("  keine Hardware-Abnahme.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
