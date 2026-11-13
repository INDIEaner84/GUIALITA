#!/usr/bin/env python3
"""Tests für scripts/eval.py — Grader und Golden Set.

Warum diese Suite wichtig ist: Jede Modell- und Rollenentscheidung ab P3 stützt
sich auf diese Urteile. Ein Grader, der zu freundlich ist, macht jede
Benchmark-Zahl wertlos. Die Tests prüfen deshalb besonders die **Ablehnungen**.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))

import eval as evalmod  # noqa: E402
import build_golden  # noqa: E402


class FakeResponse:
    """Minimaler urlopen-Ersatz für den LiveBackend-Test."""

    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def task(**expect):
    return {"id": "t", "role": "router", "prompt": "x", "expect": expect,
            "stub": {"response": "", "outcome": "pass"}}


class TestEquals(unittest.TestCase):

    def test_exact_label_passes(self):
        ok, reasons = evalmod.grade(task(equals="chat"), "chat", 10)
        self.assertTrue(ok, reasons)

    def test_whitespace_and_case_tolerated(self):
        ok, _ = evalmod.grade(task(equals="chat"), "  Chat \n", 10)
        self.assertTrue(ok)

    def test_extra_words_fail(self):
        ok, reasons = evalmod.grade(task(equals="chat"), "chat, eine Begruessung", 10)
        self.assertFalse(ok)
        self.assertTrue(any("erwartet genau" in r for r in reasons))


class TestOtherGraders(unittest.TestCase):

    def test_one_of(self):
        self.assertTrue(evalmod.grade(task(one_of=["plan", "code"]), "code", 1)[0])
        self.assertFalse(evalmod.grade(task(one_of=["plan", "code"]), "audit", 1)[0])

    def test_must_not_contain_is_case_insensitive(self):
        ok, reasons = evalmod.grade(task(must_not_contain=["OpenAI"]),
                                    "wir nutzen die openai api", 1)
        self.assertFalse(ok)
        self.assertTrue(any("verbotenes Muster" in r for r in reasons))

    def test_regex_multiline(self):
        numbered = "1. eins\n2. zwei"
        self.assertTrue(evalmod.grade(task(regex=["(?m)^2[.)]"]), numbered, 1)[0])
        self.assertFalse(evalmod.grade(task(regex=["(?m)^2[.)]"]), "eins zwei", 1)[0])

    def test_contains_requires_all_terms(self):
        self.assertTrue(evalmod.grade(task(contains=["lokal", "audio"]),
                                      "lokal und audio", 1)[0])
        self.assertFalse(evalmod.grade(task(contains=["lokal", "audio"]),
                                       "nur lokal", 1)[0])

    def test_latency_bound(self):
        self.assertTrue(evalmod.grade(task(max_latency_ms=100), "x", 99)[0])
        self.assertFalse(evalmod.grade(task(max_latency_ms=100), "x", 101)[0])


class TestJsonGraders(unittest.TestCase):

    def test_plain_json(self):
        ok, _ = evalmod.grade(task(json_keys=["verdict"]),
                              '{"verdict": "pass"}', 1)
        self.assertTrue(ok)

    def test_json_inside_code_fence(self):
        text = 'Hier:\n```json\n{"verdict": "pass", "evidence": ["a"]}\n```'
        self.assertTrue(evalmod.grade(task(json_keys=["verdict", "evidence"]), text, 1)[0])

    def test_json_with_preamble(self):
        text = 'Mein Urteil lautet: {"verdict": "fail"} — fertig.'
        self.assertTrue(evalmod.grade(task(json_keys=["verdict"]), text, 1)[0])

    def test_missing_key_fails(self):
        ok, reasons = evalmod.grade(task(json_keys=["verdict"]), '{"evidence": []}', 1)
        self.assertFalse(ok)
        self.assertTrue(any("fehlt" in r for r in reasons))

    def test_not_json_fails(self):
        ok, reasons = evalmod.grade(task(json_keys=["verdict"]), "alles gut", 1)
        self.assertFalse(ok)
        self.assertTrue(any("kein JSON" in r for r in reasons))

    def test_one_of_field(self):
        spec = task(one_of_field={"field": "verdict", "values": ["pass", "fail"]})
        self.assertTrue(evalmod.grade(spec, '{"verdict": "pass"}', 1)[0])
        self.assertFalse(evalmod.grade(spec, '{"verdict": "vielleicht"}', 1)[0])

    def test_extract_json_returns_none_on_garbage(self):
        self.assertIsNone(evalmod.extract_json("kein json hier"))


class TestGoldenSet(unittest.TestCase):

    def test_shipped_golden_set_is_valid(self):
        golden = evalmod.load_golden()
        self.assertGreaterEqual(len(golden["tasks"]), 10)
        ids = [t["id"] for t in golden["tasks"]]
        self.assertEqual(len(ids), len(set(ids)), "Aufgaben-IDs nicht eindeutig")

    def test_has_negative_controls(self):
        golden = evalmod.load_golden()
        negatives = [t for t in golden["tasks"] if t["stub"]["outcome"] == "fail"]
        self.assertGreaterEqual(len(negatives), 3,
                                "Ohne negative Kontrollen prüft das Harness nur Zustimmung")

    def test_harness_selftest_passes(self):
        """Die entscheidende Prüfung: urteilt das Harness wie erwartet?"""
        golden = evalmod.load_golden()
        report = evalmod.run_dry(golden["tasks"], evalmod.StubBackend({}))
        summary = evalmod.summarize(report)
        broken = [r for r in report["results"] if r["harness"] != "ok"]
        self.assertTrue(summary["ok"], f"Harness weicht ab bei: {broken}")

    def test_load_golden_rejects_missing_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"tasks": [{"id": "x"}]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                evalmod.load_golden(path)

    def test_load_golden_rejects_invalid_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"tasks": [{
                "id": "x", "role": "router", "prompt": "p", "expect": {},
                "stub": {"response": "y", "outcome": "maybe"}}]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                evalmod.load_golden(path)


class TestMinListLen(unittest.TestCase):

    def test_enough_entries_passes(self):
        spec = task(json_keys=["verdict", "evidence"],
                    min_list_len={"field": "evidence", "min": 1})
        ok, reasons = evalmod.grade(spec, '{"verdict":"pass","evidence":["a"]}', 1)
        self.assertTrue(ok, reasons)

    def test_empty_list_fails(self):
        spec = task(json_keys=["verdict", "evidence"],
                    min_list_len={"field": "evidence", "min": 1})
        ok, reasons = evalmod.grade(spec, '{"verdict":"pass","evidence":[]}', 1)
        self.assertFalse(ok)
        self.assertTrue(any("mindestens 1" in r for r in reasons))

    def test_non_list_field_fails(self):
        spec = task(json_keys=["verdict"],
                    min_list_len={"field": "evidence", "min": 1})
        ok, reasons = evalmod.grade(spec, '{"verdict":"pass","evidence":"eins"}', 1)
        self.assertFalse(ok)
        self.assertTrue(any("keine Liste" in r for r in reasons))


class TestStatisticsAndComparison(unittest.TestCase):

    def test_percentile_p50_and_p95(self):
        values = [10.0, 20.0, 30.0, 40.0]
        self.assertEqual(evalmod.percentile(values, 50), 25.0)
        self.assertEqual(evalmod.percentile(values, 95), 38.5)

    def test_percentile_empty_is_none(self):
        self.assertIsNone(evalmod.percentile([], 95))

    def test_summary_has_p50_p95_max(self):
        report = {"mode": "live", "results": [
            {"graded": "pass", "latency_ms": 100},
            {"graded": "pass", "latency_ms": 200},
            {"graded": "fail", "latency_ms": 300},
        ]}
        summary = evalmod.summarize(report)
        self.assertEqual(summary["p50_latency_ms"], 200.0)
        self.assertEqual(summary["median_latency_ms"], 200.0)
        self.assertEqual(summary["p95_latency_ms"], 290.0)
        self.assertEqual(summary["max_latency_ms"], 300.0)

    def test_compare_reports_reports_deltas(self):
        left = {"mode": "live", "golden": "evals/golden.json",
                "configuration": {"model": "granite-3b"},
                "results": [{"graded": "pass", "latency_ms": 100},
                            {"graded": "pass", "latency_ms": 200}]}
        right = {"mode": "live", "golden": "evals/golden.json",
                 "configuration": {"model": "granite-8b"},
                 "results": [{"graded": "pass", "latency_ms": 150},
                             {"graded": "fail", "latency_ms": 250}]}
        comparison = evalmod.compare_reports(left, right)
        self.assertEqual(comparison["left"]["label"], "granite-3b")
        self.assertEqual(comparison["right"]["label"], "granite-8b")
        self.assertEqual(comparison["delta"]["score_pct"], -50.0)
        self.assertEqual(comparison["delta"]["p50_latency_ms"], 50.0)
        self.assertEqual(comparison["warnings"], [])

    def test_compare_reports_rejects_dry_run(self):
        with self.assertRaises(ValueError):
            evalmod.compare_reports({"mode": "dry-run", "results": []},
                                    {"mode": "live", "results": []})

    def test_print_comparison_handles_missing_latency(self):
        left = {"mode": "live", "golden": "evals/golden.json",
                "configuration": {"model": "A"}, "results": [{"graded": "fail"}]}
        right = {"mode": "live", "golden": "evals/golden.json",
                 "configuration": {"model": "B"}, "results": [{"graded": "fail"}]}
        comparison = evalmod.compare_reports(left, right)
        evalmod.print_comparison(comparison)  # darf nicht mit None-Typen scheitern


class TestGeneratedSuites(unittest.TestCase):

    def test_build_golden_check_matches_shipped_files(self):
        self.assertEqual(build_golden.check(), [])

    def test_all_role_suites_have_negative_controls(self):
        for role in build_golden.SUITE_ORDER:
            suite = evalmod.load_golden(build_golden.ROLE_DIR / f"{role}.json")
            negatives = [t for t in suite["tasks"] if t["stub"]["outcome"] == "fail"]
            self.assertGreater(len(negatives), 0, f"{role}: keine negative Kontrolle")

    def test_role_suite_files_are_role_specific(self):
        for role in build_golden.SUITE_ORDER:
            suite = evalmod.load_golden(build_golden.ROLE_DIR / f"{role}.json")
            self.assertEqual(suite.get("role"), role)
            for item in suite["tasks"]:
                self.assertEqual(item["role"], role)

    def test_live_backend_honours_model_override(self):
        backend = evalmod.LiveBackend(
            "http://backend.invalid",
            {"router": {"model": "granite-3b", "prompt": "Nur ein Label."}},
            model_override="granite-8b")
        task_data = {"id": "t", "role": "router", "prompt": "Hallo"}
        with mock.patch.object(evalmod.urllib.request, "urlopen",
                               return_value=FakeResponse({"response": "chat"})) as opened:
            response, _ = backend.ask(task_data)
        self.assertEqual(response, "chat")
        request = opened.call_args[0][0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["model"], "granite-8b")
        self.assertIn("Nur ein Label.", payload["message"])



if __name__ == "__main__":
    unittest.main(verbosity=2)
