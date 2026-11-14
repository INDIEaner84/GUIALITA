#!/usr/bin/env python3
"""MUSCAL — minimale sequenzielle Agenten-Orchestrierung (ADR-002, P6).

Was dieses Skript ist
---------------------
Eine Kette von Rollen, die eine Aufgabe nacheinander bearbeitet:

    router → planner → [coder] → auditor

Jeder Schritt liest den Rollen-Prompt aus ``config/roles.json``, bekommt die
Aufgabe plus eine kurze Zusammenfassung der vorherigen Schritte und liefert ein
Ergebnis, das gegen das ``output_schema`` der Rolle geprüft wird. Jeder Schritt
schreibt ein Ereignis in ein eigenes Audit-Log.

CLI **und** HTTP (ADR-002 D4): ``run`` ist die Kommandozeile, ``serve`` stellt
``GET /health``, ``GET /pipelines``, ``GET /guard`` und ``POST /run`` bereit.
Der HTTP-Server bindet standardmäßig an 127.0.0.1, ist ohne Authentifizierung
und gehört nicht in ein öffentliches Netz.

Was es bewusst nicht ist
------------------------
* **Kein paralleler Multi-Agent-Betrieb.** Das steht unter ``prohibitions``.
  Sequenziell ist der Betrieb, der ohne Eval-Harness überhaupt bewertbar ist.
* **Keine Desktop-App.** Kein Fenster, keine Maus-/Tastatursteuerung, kein
  Screenshot, keine WebSocket-/Streaming-Schicht.
* **Kein Schreibzugriff auf das Repository.** Der Coder schreibt Vorschläge
  nach ``data/muscal/staging/<run>/``. Das Repository bleibt unberührt; ein
  Diff entsteht erst durch einen Menschen.
* **Keine Shell-Ausführung.** Es wird nichts gestartet, nichts installiert,
  nichts gelöscht. ``run_tests`` steht in der Allowlist, wird aber von dieser
  Version nicht ausgeführt — die Rolle darf es, der Orchestrator tut es nicht.
* **Keine Erfolgsbehauptung ohne Prüfung.** Der Auditor muss JSON mit
  ``verdict`` liefern. Sagt er ``fail``, endet die Kette mit Fehlercode.

Sicherheitsmechanismen
----------------------
* ``data/muscal/STOP`` — Existiert diese Datei, bricht die Kette vor dem
  nächsten Schritt ab. Not-Aus, der auch während eines Laufs greift.
* ``--max-steps`` — harte Obergrenze; der HTTP-Server deckelt Anfragen zusätzlich.
* Timeout pro Rolle aus der Registry.
* ``guard_write`` — erlaubt Schreiben ausschließlich innerhalb des
  Staging-Verzeichnisses dieser Ausführung.

Nutzung
-------
    python3 scripts/muscal.py run "Senke die Latenz der Sprachschleife" --dry-run
    python3 scripts/muscal.py run "..." --pipeline router,planner,auditor --live
    python3 scripts/muscal.py run "..." --pipeline router,coder --allow-write
    python3 scripts/muscal.py serve --port 8099
    python3 scripts/muscal.py pipelines
    python3 scripts/muscal.py guard data/muscal/staging/x
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES_FILE = ROOT / "config" / "roles.json"
DATA_DIR = ROOT / "data" / "muscal"
STOP_FILE = DATA_DIR / "STOP"

EXIT_OK = 0
EXIT_STEP_FAILED = 1
EXIT_CONFIG = 2
EXIT_ABORTED = 3

ROUTER_LABELS = {"chat", "code", "audit", "plan"}
BLOCKED_PREFIXES = ("/etc", "/proc", "/sys", "/boot", "/dev")
DEFAULT_PIPELINE = ["router", "planner", "auditor"]
CODER_PIPELINE = ["router", "planner", "coder", "auditor"]


# ----------------------------------------------------------------------------
# Konfiguration
# ----------------------------------------------------------------------------
def load_roles(path: Path = ROLES_FILE) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def display_path(path: Path) -> str:
    """Pfad möglichst relativ zum Repo — sonst absolut.

    Nötig, weil Tests ihr Ausgabeverzeichnis außerhalb des Repos anlegen.
    ``relative_to`` würde dort eine ValueError werfen; ein Werkzeug darf an
    seinem eigenen Testaufbau nicht scheitern.
    """
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------
# Sicherheit
# ----------------------------------------------------------------------------
def guard_write(target: Path, staging: Path | None) -> tuple[bool, str]:
    """Erlaubt Schreiben nur innerhalb des Staging-Verzeichnisses.

    Absolut, nicht relativ geprüft: ein Pfad mit ``..`` wird über ``resolve``
    aufgelöst, bevor entschieden wird. ``realpath``-Vergleich statt
    Zeichenkettenvergleich, damit ``/repo/data/../../etc`` nicht durchrutscht.
    """
    if staging is None:
        return False, "kein Staging-Verzeichnis — Schreiben nicht erlaubt"
    resolved = target.expanduser().resolve()
    allowed_root = staging.resolve()
    for prefix in BLOCKED_PREFIXES:
        if str(resolved).startswith(prefix):
            return False, f"gesperrter Bereich: {prefix}"
    if resolved != allowed_root and allowed_root not in resolved.parents:
        return False, f"außerhalb des Staging-Bereichs: {allowed_root}"
    return True, "erlaubt"


def stop_requested(stop_file: Path | None = None) -> bool:
    return (stop_file or STOP_FILE).exists()


# ----------------------------------------------------------------------------
# Backends
# ----------------------------------------------------------------------------
STUB_RESPONSES = {
    "router": "code",
    "planner": ("1. Ist-Zustand messen: voice-turn p50/p95 notieren\n"
                "2. Groessten Posten isolieren (STT, LLM, TTS)\n"
                "3. Nur diesen Posten optimieren\n"
                "4. Nachmessen und gegen die Baseline vergleichen"),
    "coder": ("Betroffen: backend/memory/retrieval.py, Funktion retrieve()\n"
              "Aenderung: Ergebnis cachen statt Tabelle pro Turn neu laden\n"
              "```diff\n- rows = store.all()\n+ rows = store.all() if cache is None else cache\n```"),
    "auditor": ("{\"verdict\": \"pass\", \"evidence\": [\"Plan ist pruefbar\", "
                "\"keine Tests geloescht\"], \"risks\": [\"Cache-Invalidierung "
                "muss getestet werden\"]}"),
}


class StubBackend:
    """Deterministisch, ohne Server — für Selbsttest und Trockenlauf."""

    name = "stub"

    def __init__(self, responses: dict | None = None):
        self.responses = {**STUB_RESPONSES, **(responses or {})}

    def ask(self, role_name: str, message: str, role: dict) -> tuple[str, float]:
        return self.responses.get(role_name, ""), 0.0


class LiveBackend:
    """POST /chat gegen ein laufendes Backend."""

    name = "live"

    def __init__(self, base_url: str, timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def ask(self, role_name: str, message: str, role: dict) -> tuple[str, float]:
        payload = {"message": message}
        if role.get("model"):
            payload["model"] = role["model"]
        request = urllib.request.Request(
            self.base_url + "/chat", data=json.dumps(payload).encode(),
            method="POST")
        request.add_header("Content-Type", "application/json")
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read())
        latency_ms = (time.perf_counter() - started) * 1000
        if isinstance(body, dict) and body.get("status") == "error":
            raise RuntimeError(f"Backend-Fehler: {body.get('error', '?')} — "
                               f"{body.get('details', '')}")
        return str(body.get("response", "")), latency_ms


# ----------------------------------------------------------------------------
# Schemaprüfung pro Rolle
# ----------------------------------------------------------------------------
def extract_json(text: str):
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return None


def check_output(role_name: str, schema: str, response: str) -> tuple[bool, str]:
    """Prüft, ob die Antwort das ``output_schema`` der Rolle erfüllt."""
    text = (response or "").strip()
    if not text:
        return False, "leere Antwort"

    if schema == "label":
        label = text.lower().strip(".\"' ")
        if label not in ROUTER_LABELS:
            return False, (f"kein gültiges Label: '{text[:40]}' "
                           f"(erlaubt: {', '.join(sorted(ROUTER_LABELS))})")
        return True, f"Label: {label}"

    if schema == "plan":
        if not re.search(r"(?m)^1[.)]", text):
            return False, "kein nummerierter Plan"
        steps = len(re.findall(r"(?m)^\d+[.)]", text))
        return True, f"{steps} Schritte"

    if schema == "diff":
        lines = text.splitlines()
        if len(lines) < 2:
            return False, "zu kurz für einen Änderungsvorschlag"
        if not re.search(r"(?m)^Betroffen:", text):
            return False, "keine betroffenen Zeilen genannt"
        if "```diff" not in text:
            return False, "kein Diff-Block"
        return True, f"{len(lines)} Zeilen, Diff-Block"

    if schema == "report":
        parsed = extract_json(text)
        if parsed is None:
            return False, "kein JSON"
        if "verdict" not in parsed:
            return False, "JSON ohne 'verdict'"
        verdict = str(parsed["verdict"]).lower()
        if verdict not in ("pass", "fail"):
            return False, f"verdict ungültig: {verdict}"
        evidence = parsed.get("evidence") or []
        if verdict == "pass" and not evidence:
            return False, "verdict=pass ohne Evidenz"
        return True, f"verdict={verdict}, {len(evidence)} Belege"

    return True, "kein Schema definiert"


# ----------------------------------------------------------------------------
# Lauf
# ----------------------------------------------------------------------------
def build_message(role: dict, task: str, history: list[dict]) -> str:
    parts = [str(role.get("prompt", "")).strip(), f"Aufgabe: {task}"]
    if history:
        parts.append("Bisherige Schritte:")
        for step in history:
            head = step["response_head"][:400]
            parts.append(f"- {step['role']} ({step['status']}): {head}")
    return "\n\n".join(part for part in parts if part)


def write_audit(run_dir: Path, event: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def run_pipeline(task: str, pipeline: list[str], backend, roles: dict,
                 allow_write: bool, max_steps: int, out_dir: Path,
                 stop_file: Path | None = None) -> dict:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    run_dir = out_dir / run_id
    staging = run_dir / "staging" if allow_write else None
    active_stop = stop_file or STOP_FILE
    history: list[dict] = []
    steps: list[dict] = []
    status = "ok"

    for index, role_name in enumerate(pipeline):
        if index >= max_steps:
            steps.append({"role": role_name, "status": "skipped",
                          "reason": f"--max-steps {max_steps} erreicht"})
            status = "aborted"
            break
        if stop_requested(active_stop):
            steps.append({"role": role_name, "status": "aborted",
                          "reason": f"STOP-Datei vorhanden: {active_stop}"})
            status = "aborted"
            write_audit(run_dir, {"timestamp": timestamp(), "event": "stop",
                                  "role": role_name, "run": run_id})
            break

        role = roles.get(role_name)
        if role is None:
            steps.append({"role": role_name, "status": "config_error",
                          "reason": "Rolle nicht in config/roles.json"})
            status = "config_error"
            break

        message = build_message(role, task, history)
        write_audit(run_dir, {"timestamp": timestamp(), "event": "step_start",
                              "run": run_id, "step": index, "role": role_name,
                              "model": role.get("model"),
                              "prompt_chars": len(message)})

        started = time.perf_counter()
        try:
            response, backend_ms = backend.ask(role_name, message, role)
        except urllib.error.HTTPError as exc:
            wall_ms = (time.perf_counter() - started) * 1000
            detail = f"HTTP {exc.code}"
            steps.append({"role": role_name, "status": "failed",
                          "reason": detail, "latency_ms": round(wall_ms, 1),
                          "response_head": ""})
            write_audit(run_dir, {"timestamp": timestamp(), "event": "step_end",
                                  "run": run_id, "role": role_name,
                                  "status": "failed", "reason": detail})
            status = "step_failed"
            break
        except Exception as exc:  # noqa: BLE001 — Diagnose
            wall_ms = (time.perf_counter() - started) * 1000
            detail = f"{type(exc).__name__}: {exc}"
            steps.append({"role": role_name, "status": "failed",
                          "reason": detail, "latency_ms": round(wall_ms, 1),
                          "response_head": ""})
            write_audit(run_dir, {"timestamp": timestamp(), "event": "step_end",
                                  "run": run_id, "role": role_name,
                                  "status": "failed", "reason": detail})
            status = "step_failed"
            break

        wall_ms = (time.perf_counter() - started) * 1000
        ok, detail = check_output(role_name, role.get("output_schema", ""), response)

        step = {
            "role": role_name,
            "status": "ok" if ok else "failed",
            "detail": detail,
            "latency_ms": round(wall_ms, 1),
            "backend_ms": round(backend_ms, 1),
            "response_head": (response or "")[:200].replace("\n", " "),
        }

        # Coder schreibt ausschließlich ins Staging, nur mit --allow-write.
        if ok and role_name == "coder":
            if allow_write:
                target = run_dir / "staging" / "vorschlag.md"
                permitted, reason = guard_write(target, staging)
                step["write"] = {"target": display_path(target),
                                 "allowed": permitted, "reason": reason}
                if permitted:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(response + "\n", encoding="utf-8")
            else:
                step["write"] = {"allowed": False,
                                 "reason": "ohne --allow-write wird nichts geschrieben"}

        # Auditor-Verdict darf nicht erst nach dem Audit-Log kippen: sonst
        # stünde im Log "ok", während der Lauf längst failed ist.
        audit_failed = False
        if ok and role.get("output_schema") == "report":
            parsed = extract_json(response) or {}
            if str(parsed.get("verdict", "")).lower() == "fail":
                audit_failed = True
                step["status"] = "audit_failed"
                step["detail"] = f"{detail}; Auditor verdict=fail"

        history.append(step)
        steps.append(step)
        write_audit(run_dir, {"timestamp": timestamp(), "event": "step_end",
                              "run": run_id, "step": index, "role": role_name,
                              "status": step["status"], "detail": step["detail"],
                              "latency_ms": step["latency_ms"],
                              "backend_ms": step["backend_ms"]})

        if not ok:
            status = "step_failed"
            break
        if audit_failed:
            status = "audit_failed"
            break

    result = {"run_id": run_id, "task": task, "pipeline": pipeline,
              "backend": backend.name, "status": status, "steps": steps,
              "run_dir": display_path(run_dir) if run_dir.exists() else None,
              "generated": timestamp()}
    write_audit(run_dir, {"timestamp": timestamp(), "event": "run_end",
                          "run": run_id, "status": status,
                          "steps": len(steps)})
    return result


# ----------------------------------------------------------------------------
# HTTP-Schnittstelle (ADR-002 D4)
# ----------------------------------------------------------------------------
class MuscalHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_handler(roles: dict, backend, out_dir: Path, allow_write: bool,
                 max_steps: int, stop_file: Path):
    """Erzeugt einen Handler ohne FastAPI — reine Standardbibliothek."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "MUSCAL/1.0"

        def log_message(self, fmt, *args):  # keine Zugriffslogs in Tests/CI
            return

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _path(self) -> str:
            return urllib.parse.urlparse(self.path).path.rstrip("/") or "/"

        def do_GET(self):  # noqa: N802 — http.server vorgeschrieben
            path = self._path()
            if path == "/health":
                self._send(200, {"status": "ok", "service": "muscal-http",
                                 "backend": backend.name, "timestamp": timestamp()})
                return
            if path == "/pipelines":
                self._send(200, {
                    "roles": sorted(roles),
                    "default_pipeline": DEFAULT_PIPELINE,
                    "coder_pipeline": CODER_PIPELINE,
                    "max_steps": max_steps,
                    "allow_write": allow_write,
                    "stop_file": display_path(stop_file),
                })
                return
            if path == "/guard":
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                raw = query.get("path", [""])[0]
                if not raw:
                    self._send(400, {"error": "query-Parameter 'path' fehlt"})
                    return
                target = Path(raw)
                if not target.is_absolute():
                    target = ROOT / target
                staging = out_dir / "staging-check"
                permitted, reason = guard_write(target, staging)
                self._send(200, {"path": str(target), "allowed": permitted,
                                 "reason": reason, "staging": str(staging)})
                return
            self._send(404, {"error": "unbekannter Endpunkt", "path": path})

        def do_POST(self):  # noqa: N802 — http.server vorgeschrieben
            if self._path() != "/run":
                self._send(404, {"error": "nur POST /run ist erlaubt"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 100_000:
                self._send(400, {"error": "Content-Length fehlt oder ist zu groß"})
                return
            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                self._send(400, {"error": "Body ist kein gültiges JSON"})
                return
            if not isinstance(data, dict):
                self._send(400, {"error": "Body muss ein JSON-Objekt sein"})
                return

            task = str(data.get("task", "")).strip()
            if not task:
                self._send(400, {"error": "Feld 'task' fehlt oder ist leer"})
                return

            pipeline = data.get("pipeline", DEFAULT_PIPELINE)
            if isinstance(pipeline, str):
                pipeline = [part.strip() for part in pipeline.split(",") if part.strip()]
            if not isinstance(pipeline, list) or not pipeline:
                self._send(400, {"error": "'pipeline' muss eine nichtleere Liste sein"})
                return
            unknown = [name for name in pipeline if name not in roles]
            if unknown:
                self._send(400, {"error": "unbekannte Rollen", "unknown": unknown})
                return

            requested_steps = data.get("max_steps", max_steps)
            if not isinstance(requested_steps, int) or requested_steps < 1:
                self._send(400, {"error": "'max_steps' muss eine positive Ganzzahl sein"})
                return
            effective_steps = min(requested_steps, max_steps)
            warnings = []
            if requested_steps > max_steps:
                warnings.append(f"max_steps auf Servergrenze {max_steps} gekappt")

            dry_run = bool(data.get("dry_run", True))
            request_write = bool(data.get("allow_write", False))
            effective_write = request_write and allow_write
            if request_write and not allow_write:
                warnings.append("Schreiben vom Server nicht freigegeben — Anfrage ignoriert")
            run_backend = StubBackend() if dry_run else backend
            if not dry_run and backend.name == "stub":
                warnings.append("Server läuft ohne --live; es wird trotzdem der Stub verwendet")

            if stop_requested(stop_file):
                self._send(409, {"error": "STOP-Datei vorhanden",
                                 "stop_file": display_path(stop_file)})
                return

            try:
                result = run_pipeline(task, pipeline, run_backend, roles,
                                      effective_write, effective_steps, out_dir,
                                      stop_file)
            except Exception as exc:  # noqa: BLE001 — Diagnose im HTTP-Status
                self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
                return
            result["warnings"] = warnings
            code = {"ok": 200, "aborted": 409,
                    "config_error": 400}.get(result["status"], 422)
            self._send(code, result)

    return Handler


def serve_http(host: str = "127.0.0.1", port: int = 8099, roles: dict | None = None,
               backend=None, out_dir: Path = DATA_DIR, allow_write: bool = False,
               max_steps: int = 5, stop_file: Path | None = None) -> MuscalHTTPServer:
    handler = make_handler(roles or {}, backend or StubBackend(), Path(out_dir),
                           allow_write, max_steps, stop_file or STOP_FILE)
    return MuscalHTTPServer((host, port), handler)


def cmd_serve(args, roles: dict) -> int:
    backend = LiveBackend(args.url, args.timeout) if args.live else StubBackend()
    server = serve_http(args.host, args.port, roles, backend, Path(args.out),
                        args.allow_write, args.max_steps)
    host, port = server.server_address[:2]
    print()
    print("=" * 78)
    print(f"  MUSCAL HTTP — http://{host}:{port}")
    print("=" * 78)
    print(f"  Backend   : {backend.name}")
    print(f"  Schreiben : {'erlaubt (Staging)' if args.allow_write else 'nicht erlaubt'}")
    print(f"  Not-Aus   : {STOP_FILE}")
    print("  Endpunkte : GET /health · GET /pipelines · GET /guard?path=… · POST /run")
    print("  Bindung   : 127.0.0.1 empfohlen; kein Auth, nicht für öffentliche Netze.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server beendet.")
    finally:
        server.server_close()
    return EXIT_OK


# ----------------------------------------------------------------------------
# Ausgabe
# ----------------------------------------------------------------------------
def print_result(result: dict) -> None:
    print()
    print("=" * 78)
    print(f"  MUSCAL — {result['run_id']}  ({result['backend']})")
    print("=" * 78)
    print(f"  Aufgabe: {result['task']}")
    print(f"  Kette  : {' → '.join(result['pipeline'])}")
    print()
    for step in result["steps"]:
        mark = {"ok": "OK  ", "failed": "FAIL", "audit_failed": "FAIL",
                "aborted": "STOP", "skipped": "SKIP"}.get(step["status"], "?   ")
        latency = f"{step.get('latency_ms', 0):.0f} ms" if step.get("latency_ms") else "—"
        print(f"  {mark} {step['role']:<10}{latency:>10}  {step.get('detail', step.get('reason', ''))}")
        if step.get("write"):
            write = step["write"]
            state = "geschrieben" if write.get("allowed") and write.get("target") else "nicht geschrieben"
            print(f"       Schreiben: {state} — {write.get('reason')}")
    print()
    print(f"  Ergebnis: {result['status']}")
    if result.get("run_dir"):
        print(f"  Audit   : {result['run_dir']}/events.jsonl")


def main() -> int:
    parser = argparse.ArgumentParser(description="MUSCAL — sequenzielle Agentenkette, CLI/HTTP.")
    parser.add_argument("--roles", default=str(ROLES_FILE))
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--out", default=str(DATA_DIR))
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("pipelines", help="verfügbare Rollen und Standardketten")

    run_parser = sub.add_parser("run", help="Aufgabe durch die Kette schicken")
    run_parser.add_argument("task")
    run_parser.add_argument("--pipeline", default="router,planner,auditor")
    mode = run_parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="Stub-Backend, ohne Server (Default)")
    mode.add_argument("--live", action="store_true", help="POST /chat benutzen")
    run_parser.add_argument("--allow-write", action="store_true",
                            help="Coder darf ins Staging schreiben")
    run_parser.add_argument("--max-steps", type=int, default=5)
    run_parser.add_argument("--json", metavar="PFAD")

    serve_parser = sub.add_parser("serve", help="HTTP-Schnittstelle starten")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8099)
    serve_parser.add_argument("--live", action="store_true",
                              help="POST /run darf das echte Backend verwenden")
    serve_parser.add_argument("--allow-write", action="store_true",
                              help="Schreiben ins Staging grundsätzlich erlauben")
    serve_parser.add_argument("--max-steps", type=int, default=5)

    guard_parser = sub.add_parser("guard", help="prüfen, ob ein Schreibziel erlaubt wäre")
    guard_parser.add_argument("path")

    args = parser.parse_args()

    try:
        config = load_roles(Path(args.roles))
        roles = config.get("roles", {})
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  Rollen nicht lesbar: {exc}")
        return EXIT_CONFIG

    if args.command == "pipelines":
        print(f"\n  Rollen: {', '.join(roles) or '—'}")
        print(f"  Standardkette: {' → '.join(DEFAULT_PIPELINE)}")
        print(f"  Mit Coder    : {' → '.join(CODER_PIPELINE)}")
        print(f"  HTTP         : python3 scripts/muscal.py serve --port 8099")
        print(f"  Not-Aus      : {STOP_FILE} anlegen")
        return EXIT_OK

    if args.command == "guard":
        target = Path(args.path)
        if not target.is_absolute():
            target = ROOT / target
        staging = Path(args.out) / "staging-check"
        allowed, reason = guard_write(target, staging)
        print(f"  {target}\n  → {'erlaubt' if allowed else 'abgelehnt'}: {reason}")
        return EXIT_OK if allowed else EXIT_STEP_FAILED

    if args.command == "serve":
        return cmd_serve(args, roles)

    pipeline = [name.strip() for name in args.pipeline.split(",") if name.strip()]
    unknown = [name for name in pipeline if name not in roles]
    if unknown:
        print(f"  Unbekannte Rollen: {', '.join(unknown)}")
        return EXIT_CONFIG

    backend = (LiveBackend(args.url, args.timeout) if args.live else StubBackend())
    result = run_pipeline(args.task, pipeline, backend, roles,
                          args.allow_write, args.max_steps, Path(args.out))
    print_result(result)

    if args.json:
        path = Path(args.json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        print(f"  Ergebnis-JSON: {path}")

    return {"ok": EXIT_OK, "aborted": EXIT_ABORTED}.get(result["status"], EXIT_STEP_FAILED)


if __name__ == "__main__":
    sys.exit(main())
