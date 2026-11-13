#!/usr/bin/env python3
"""Tests für scripts/modelsctl.py — VRAM-Budget und Wechselplanung.

Der Kern: Das Budget muss dreiwertig urteilen (passt / zu groß / unbekannt).
Eine zweiwertige Antwort würde bei fehlenden Modellgrößen "passt" behaupten —
und genau das ist der Fehler, der später als CUDA-Out-of-Memory auftaucht.
"""
import os
import sys
import types
import unittest
from unittest import mock

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))

import modelsctl  # noqa: E402

BUDGET = {
    "overhead_gb": 0.8,
    "kv_reserve_gb": 1.0,
    "gpu": {"total_gb": 11.0},
    "models": {
        "small": {"weights_gb": 2.0},
        "big": {"weights_gb": 5.5},
        "huge": {"weights_gb": 9.5},
        "unknown": {"weights_gb": None},
    },
}


class TestSizes(unittest.TestCase):

    def test_declared_size(self):
        self.assertEqual(modelsctl.model_size_gb("small", BUDGET), 2.0)

    def test_live_size_wins(self):
        self.assertEqual(modelsctl.model_size_gb("small", BUDGET, {"small": 2.4}), 2.4)

    def test_missing_size_is_none_not_zero(self):
        self.assertIsNone(modelsctl.model_size_gb("unknown", BUDGET))
        self.assertIsNone(modelsctl.model_size_gb("gibtsnicht", BUDGET))

    def test_needed_includes_overhead_and_reserve(self):
        need, unknown = modelsctl.needed_gb(["small"], BUDGET)
        self.assertEqual(need, 3.8)
        self.assertEqual(unknown, [])

    def test_needed_with_unknown_model_is_none(self):
        need, unknown = modelsctl.needed_gb(["small", "unknown"], BUDGET)
        self.assertIsNone(need, "Teilsumme darf nicht als Gesamtbedarf gelten")
        self.assertEqual(unknown, ["unknown"])


class TestFits(unittest.TestCase):

    def test_fits_with_headroom(self):
        verdict = modelsctl.fits(["small"], BUDGET, available_gb=11.0)
        self.assertEqual(verdict["result"], "fits")
        self.assertEqual(verdict["headroom_gb"], 7.2)

    def test_too_big(self):
        verdict = modelsctl.fits(["big", "big"], BUDGET, available_gb=11.0)
        self.assertEqual(verdict["result"], "too_big")
        self.assertGreater(verdict["excess_gb"], 0)

    def test_unknown_is_third_state(self):
        verdict = modelsctl.fits(["unknown"], BUDGET, available_gb=11.0)
        self.assertEqual(verdict["result"], "unknown")
        self.assertIn("nicht entscheidbar", verdict["reason"])

    def test_exactly_full_still_fits(self):
        # overhead 0.8 + reserve 1.0 + 9.2 = 11.0
        verdict = modelsctl.fits(["huge"], BUDGET, available_gb=11.3,
                                 live_sizes={"huge": 9.5})
        self.assertEqual(verdict["result"], "fits")
        self.assertEqual(verdict["headroom_gb"], 0.0)


class TestPlan(unittest.TestCase):

    def test_nothing_to_unload(self):
        result = modelsctl.plan("small", [], BUDGET, available_gb=11.0)
        self.assertEqual(result["unload"], [])
        self.assertEqual(result["verdict"]["result"], "fits")

    def test_unloads_until_target_fits(self):
        # big (5.5) + huge (9.5) passen nicht; huge muss weichen.
        loaded = ["big", "huge"]
        result = modelsctl.plan("big", loaded, BUDGET, available_gb=11.0)
        self.assertIn("huge", result["unload"])
        self.assertEqual(result["verdict"]["result"], "fits")

    def test_unload_order_is_lifo(self):
        loaded = ["small", "big", "huge"]
        result = modelsctl.plan("huge", loaded, BUDGET, available_gb=11.0)
        self.assertEqual(result["unload"], ["big", "small"])

    def test_blocked_when_target_alone_is_too_big(self):
        result = modelsctl.plan("huge", ["small"], BUDGET, available_gb=6.0)
        self.assertTrue(result.get("blocked"))
        self.assertEqual(result["verdict"]["result"], "too_big")


class TestEnvironment(unittest.TestCase):

    def test_free_vram_falls_back_to_declared_total(self):
        value, source = modelsctl.free_vram_gb(BUDGET)
        self.assertGreater(value, 0)
        self.assertIn(source, ("nvidia-smi", "deklariert (kein nvidia-smi)"))

    def test_load_budget_reads_repository_config(self):
        budget = modelsctl.load_budget()
        self.assertIn("granite-3b", budget["models"])
        self.assertEqual(budget["gpu"]["total_gb"], 11.0)


class TestProcessDelegation(unittest.TestCase):

    def fake_proc(self, code=0, stdout="[GUIALITA] fertig\n", stderr=""):
        return types.SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)

    def args(self, **overrides):
        values = {"yes": True, "restart": False, "url": "http://localhost:8080",
                  "script_timeout": 120.0}
        values.update(overrides)
        return types.SimpleNamespace(**values)

    def test_run_script_uses_existing_shell_script(self):
        with mock.patch.object(modelsctl.subprocess, "run",
                               return_value=self.fake_proc()) as run:
            modelsctl.run_script("start.sh", ["--restart"])
        command = run.call_args[0][0]
        self.assertEqual(command[0], "bash")
        self.assertTrue(command[1].endswith("scripts/start.sh"))
        self.assertIn("--restart", command)

    def test_start_requires_yes(self):
        self.assertEqual(modelsctl.cmd_start(self.args(yes=False)), 2)

    def test_stop_requires_yes(self):
        self.assertEqual(modelsctl.cmd_stop(self.args(yes=False)), 2)

    def test_unload_does_not_invent_an_endpoint(self):
        args = self.args()
        with mock.patch.object(modelsctl, "cmd_stop", return_value=0) as stop:
            self.assertEqual(modelsctl.cmd_unload(args), 0)
        stop.assert_called_once_with(args)

    def test_start_success_checks_health(self):
        health = {"primary_runtime": {"runtime": "llama-cpp-python",
                                      "status": "online", "gpu": "GTX 1080 Ti"}}
        with mock.patch.object(modelsctl, "run_script",
                               return_value=self.fake_proc()) as script, \
             mock.patch.object(modelsctl, "http_json", return_value=health) as http:
            self.assertEqual(modelsctl.cmd_start(self.args(restart=True)), 0)
        self.assertEqual(script.call_args[0][1], ["--restart"])
        http.assert_called_once_with("http://localhost:8080/health")

    def test_start_reports_script_failure(self):
        with mock.patch.object(modelsctl, "run_script",
                               return_value=self.fake_proc(code=1)):
            self.assertEqual(modelsctl.cmd_start(self.args()), 2)

    def test_stop_success_when_health_disappears(self):
        with mock.patch.object(modelsctl, "run_script",
                               return_value=self.fake_proc()), \
             mock.patch.object(modelsctl, "http_json",
                               side_effect=OSError("connection refused")):
            self.assertEqual(modelsctl.cmd_stop(self.args()), 0)

    def test_stop_reports_still_running_backend(self):
        with mock.patch.object(modelsctl, "run_script",
                               return_value=self.fake_proc()), \
             mock.patch.object(modelsctl, "http_json", return_value={}):
            self.assertEqual(modelsctl.cmd_stop(self.args()), 1)

    def test_health_online(self):
        health = {"primary_runtime": {"runtime": "llama-cpp-python",
                                      "status": "online", "gpu": "GTX 1080 Ti"},
                  "default_model": "granite-3b", "models": []}
        with mock.patch.object(modelsctl, "http_json", return_value=health):
            self.assertEqual(modelsctl.cmd_health("http://x"), 0)

    def test_health_offline_is_not_success(self):
        health = {"primary_runtime": {"runtime": "llama-cpp-python",
                                      "status": "offline"}, "models": []}
        with mock.patch.object(modelsctl, "http_json", return_value=health):
            self.assertEqual(modelsctl.cmd_health("http://x"), 1)



if __name__ == "__main__":
    unittest.main(verbosity=2)
