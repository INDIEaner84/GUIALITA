"""GUIALITA — zentrale Pfadauflösung.

Ein einziger Ort, an dem entschieden wird, wo Repository, Modelle, Runtime-
Binaries und externe Werkzeuge liegen. Alles ist über Umgebungsvariablen
überschreibbar; die Defaults sind repository-relativ und enthalten keine
maschinenspezifischen Annahmen.

Variablen (alle optional):

    GUIALITA_ROOT           Repository-Wurzel        (Default: dieses Repo)
    GUIALITA_MODEL_ROOT     Modelle im Repo          (Default: $GUIALITA_ROOT/models)
    GUIALITA_EXTERNAL_MODEL_ROOT
                            Modelle außerhalb des Repos (z. B. externe Platte)
                                                     (Default: $GUIALITA_MODEL_ROOT)
    GUIALITA_RUNTIME_ROOT   Runtime-Binaries         (Default: $GUIALITA_ROOT/runtime)
    GUIALITA_DATA_ROOT      SQLite/Datenablage       (Default: $GUIALITA_ROOT/data)
    GUIALITA_WHISPER_CLI    whisper.cpp-Executable   (Default: "whisper-cli" aus $PATH)

Maschinenspezifische Werte gehören in eine lokale, nicht versionierte `.env`
im Repository-Root (siehe `.env.example`). Diese wird beim Import gelesen und
überschreibt niemals bereits gesetzte Umgebungsvariablen.
"""

import os
import shutil
from typing import Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ENV_FILE = os.path.join(REPO_ROOT, ".env")
_loaded = False


def load_env_file(path: Optional[str] = None) -> None:
    """Liest eine einfache KEY=VALUE-Datei ein (keine Fremdabhängigkeit).

    Bereits gesetzte Umgebungsvariablen haben Vorrang. Fehlt die Datei,
    passiert nichts.
    """
    global _loaded
    path = path or _ENV_FILE
    if not os.path.isfile(path):
        _loaded = True
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    _loaded = True


if not _loaded:
    load_env_file()


def root() -> str:
    return os.path.abspath(os.environ.get("GUIALITA_ROOT", REPO_ROOT))


def model_root() -> str:
    return os.path.abspath(os.environ.get("GUIALITA_MODEL_ROOT", os.path.join(root(), "models")))


def external_model_root() -> str:
    """Modelle außerhalb des Repos (externe Platte, gemeinsamer Modellspeicher).

    Ohne Konfiguration identisch mit `model_root()` — das Repo bleibt damit
    aus sich heraus lauffähig.
    """
    return os.path.abspath(os.environ.get("GUIALITA_EXTERNAL_MODEL_ROOT", model_root()))


def runtime_root() -> str:
    return os.path.abspath(os.environ.get("GUIALITA_RUNTIME_ROOT", os.path.join(root(), "runtime")))


def data_root() -> str:
    return os.path.abspath(os.environ.get("GUIALITA_DATA_ROOT", os.path.join(root(), "data")))


def whisper_cli() -> str:
    """Pfad zum whisper.cpp-Executable.

    Default: `whisper-cli` aus `$PATH`. Wird es dort nicht gefunden, wird der
    unaufgelöste Name zurückgegeben — die Verfügbarkeitsprüfung im Adapter
    meldet das dann sauber als offline.
    """
    configured = os.environ.get("GUIALITA_WHISPER_CLI")
    if configured:
        return os.path.abspath(os.path.expanduser(configured))
    found = shutil.which("whisper-cli")
    return found or "whisper-cli"


_VARS = {
    "GUIALITA_ROOT": root,
    "GUIALITA_MODEL_ROOT": model_root,
    "GUIALITA_EXTERNAL_MODEL_ROOT": external_model_root,
    "GUIALITA_RUNTIME_ROOT": runtime_root,
    "GUIALITA_DATA_ROOT": data_root,
    "GUIALITA_WHISPER_CLI": whisper_cli,
}


def expand(value: str) -> str:
    """Ersetzt `${GUIALITA_*}`-Platzhalter in einem Konfigurationswert."""
    if not isinstance(value, str):
        return value
    for name, getter in _VARS.items():
        token = "${" + name + "}"
        if token in value:
            value = value.replace(token, getter())
    return os.path.expandvars(os.path.expanduser(value))


def resolve(value: str, base: Optional[str] = None) -> str:
    """Expandiert Platzhalter und macht relative Pfade absolut (Basis: Repo-Root).

    Reine Kommandonamen ohne Verzeichnistrenner (z. B. "whisper-cli") bleiben
    unverändert, damit sie über $PATH aufgelöst werden können.
    """
    if not value:
        return value
    expanded = expand(value)
    if os.sep not in expanded:
        return expanded
    if not os.path.isabs(expanded):
        expanded = os.path.join(base or root(), expanded)
    return os.path.abspath(expanded)


def describe() -> dict:
    """Aufgelöste Pfadkonfiguration — für /health und Diagnose."""
    return {name: getter() for name, getter in _VARS.items()}
