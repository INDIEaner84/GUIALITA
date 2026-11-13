#!/usr/bin/env python3
"""Tests für scripts/roles.py — Rollen-Registry.

Die wichtigste Prüfung ist die Invariante: Eine Rolle mit Audit-Aufgabe darf
kein schreibendes Tool haben. Wird sie verletzt, ist "Auditor" nur ein zweiter
Coder mit besserem Ruf.
"""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))

import roles as rolesmod  # noqa: E402
import build_roles  # noqa: E402

REAL_CONFIG = rolesmod.load_roles()


def base_config():
    return {
        "tools": {
            "read_file": {"mutating": False},
            "write_file": {"mutating": True},
        },
        "roles": {
            "auditor": {
                "description": "prüft",
                "model": "granite-3b",
                "prompt": "Prüfe die Arbeit und ändere nichts, sondern berichte.",
                "tools": ["read_file"],
                "output_schema": "report",
                "timeout_ms": 60000,
                "eval": "evals/golden.json",
            },
            "coder": {
                "description": "ändert",
                "model": "granite-3b",
                "prompt": "Ändere den Code minimal-invasiv und erkläre die Differenz.",
                "tools": ["read_file", "write_file"],
                "output_schema": "diff",
                "timeout_ms": 60000,
                "requires_approval": True,
                "eval": "evals/golden.json",
            },
        },
    }


class TestModelIds(unittest.TestCase):

    def test_reads_all_repository_models(self):
        ids = rolesmod.model_ids()
        self.assertIn("granite-3b", ids)
        self.assertIn("lfm-audio-1.5b", ids)

    def test_dotted_model_names_are_found(self):
        # lfm-vision-1.6b enthält einen Punkt; eine frühere Fassung verschluckte ihn.
        self.assertIn("lfm-vision-1.6b", rolesmod.model_ids())

    def test_missing_file_returns_empty(self):
        self.assertEqual(rolesmod.model_ids(Path("/gibt/es/nicht.yaml")), [])


class TestValidate(unittest.TestCase):

    def test_repository_config_is_consistent(self):
        problems = rolesmod.validate(REAL_CONFIG)
        self.assertEqual(problems, [], f"Rollenkonfiguration fehlerhaft: {problems}")

    def test_valid_minimal_config(self):
        problems = rolesmod.validate(base_config())
        self.assertEqual(problems, [])

    def test_auditor_must_not_write(self):
        config = base_config()
        config["roles"]["auditor"]["tools"] = ["read_file", "write_file"]
        config["roles"]["auditor"]["requires_approval"] = True
        problems = rolesmod.validate(config)
        self.assertTrue(any("Audit-Aufgabe hat mutierende Tools" in p
                            for p in problems), problems)

    def test_mutating_tool_requires_approval(self):
        config = base_config()
        del config["roles"]["coder"]["requires_approval"]
        problems = rolesmod.validate(config)
        self.assertTrue(any("ohne requires_approval" in p for p in problems), problems)

    def test_unknown_model_is_rejected(self):
        config = base_config()
        config["roles"]["coder"]["model"] = "gpt-4o"
        problems = rolesmod.validate(config)
        self.assertTrue(any("steht nicht in config/models.yaml" in p
                            for p in problems), problems)

    def test_unknown_tool_is_rejected(self):
        config = base_config()
        config["roles"]["coder"]["tools"] = ["rm_rf"]
        problems = rolesmod.validate(config)
        self.assertTrue(any("unbekannte Tools" in p for p in problems), problems)

    def test_missing_eval_suite_is_rejected(self):
        config = base_config()
        config["roles"]["coder"]["eval"] = "evals/gibtsnicht.json"
        problems = rolesmod.validate(config)
        self.assertTrue(any("Eval-Suite fehlt" in p for p in problems), problems)

    def test_short_prompt_is_rejected(self):
        config = base_config()
        config["roles"]["coder"]["prompt"] = "mach"
        problems = rolesmod.validate(config)
        self.assertTrue(any("Prompt kürzer" in p for p in problems), problems)

    def test_timeout_bounds(self):
        config = base_config()
        config["roles"]["coder"]["timeout_ms"] = 5
        problems = rolesmod.validate(config)
        self.assertTrue(any("timeout_ms außerhalb" in p for p in problems), problems)

    def test_missing_field_is_rejected(self):
        config = base_config()
        del config["roles"]["coder"]["output_schema"]
        problems = rolesmod.validate(config)
        self.assertTrue(any("Pflichtfeld fehlt: output_schema" in p
                            for p in problems), problems)

    def test_unknown_eval_role_is_rejected(self):
        config = base_config()
        config["roles"]["coder"]["eval_roles"] = ["ghost"]
        problems = rolesmod.validate(config)
        self.assertTrue(any("unbekannte Rolle 'ghost'" in p for p in problems), problems)

    def test_empty_config(self):
        self.assertEqual(rolesmod.validate({"roles": {}}), ["keine Rollen definiert"])


class TestLoad(unittest.TestCase):

    def test_load_roles_returns_dict(self):
        self.assertIsInstance(REAL_CONFIG, dict)
        self.assertIn("roles", REAL_CONFIG)

    def test_config_is_json_serialisable(self):
        json.dumps(REAL_CONFIG)  # wirft bei kaputten Strukturen

    def test_roles_have_eval_suites_that_exist(self):
        for name, role in REAL_CONFIG["roles"].items():
            path = Path(PROJECT_DIR) / role["eval"]
            self.assertTrue(path.is_file(), f"{name}: {role['eval']} fehlt")


class TestValidationDoesNotStopEarly(unittest.TestCase):

    def test_missing_field_in_one_role_does_not_skip_later_roles(self):
        config = base_config()
        del config["roles"]["coder"]["output_schema"]
        config["roles"]["auditor"]["model"] = "gpt-4o"
        problems = rolesmod.validate(config)
        self.assertTrue(any("Pflichtfeld fehlt: output_schema" in p for p in problems))
        self.assertTrue(any("auditor: Modell 'gpt-4o'" in p for p in problems),
                        "die zweite Rolle darf nicht übersprungen werden")


class TestRoleSwitch(unittest.TestCase):

    def test_switch_without_model_change(self):
        result = rolesmod.role_switch("auditor", "coder", base_config())
        self.assertFalse(result["model_switch"])
        self.assertTrue(result["shared_instance"])
        self.assertIsNone(result["measured_switch_ms"])

    def test_switch_with_model_change_is_reported(self):
        result = rolesmod.role_switch("planner", "coder", REAL_CONFIG)
        self.assertTrue(result["model_switch"])
        self.assertEqual(result["from_model"], "granite-3b")
        self.assertEqual(result["to_model"], "granite-8b")
        self.assertTrue(result["requires_approval"])

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(ValueError):
            rolesmod.role_switch("router", "ghost", REAL_CONFIG)


class TestMirrorAndSuites(unittest.TestCase):

    def test_repository_mirror_is_in_sync(self):
        self.assertEqual(rolesmod.check_mirror(Path(PROJECT_DIR)), [])
        self.assertEqual(build_roles.check(Path(PROJECT_DIR)), [])

    def test_render_contains_approval_and_mutating_flag(self):
        rendered = build_roles.render(REAL_CONFIG)
        self.assertIn("requires_approval: true", rendered)
        self.assertIn("mutating: true", rendered)
        self.assertIn("config/roles.json", rendered)

    def test_repository_eval_paths_are_role_specific(self):
        for name, role in REAL_CONFIG["roles"].items():
            self.assertEqual(role["eval"], f"evals/roles/{name}.json")
            self.assertTrue((Path(PROJECT_DIR) / role["eval"]).is_file())

    def test_check_eval_suite_detects_mismatched_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "suite.json").write_text(json.dumps({
                "role": "auditor",
                "tasks": [{"id": "x", "role": "auditor", "prompt": "p",
                           "expect": {}, "stub": {"response": "x", "outcome": "fail"}}]
            }), encoding="utf-8")
            problems = rolesmod.check_eval_suite(
                "router", {"eval": "suite.json", "eval_roles": ["router"]}, root)
            self.assertTrue(any("nennt role='auditor'" in p for p in problems))

    def test_check_eval_suite_requires_negative_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "suite.json").write_text(json.dumps({
                "role": "router",
                "tasks": [{"id": "x", "role": "router", "prompt": "p",
                           "expect": {}, "stub": {"response": "chat", "outcome": "pass"}}]
            }), encoding="utf-8")
            problems = rolesmod.check_eval_suite(
                "router", {"eval": "suite.json", "eval_roles": ["router"]}, root)
            self.assertTrue(any("ohne negative Kontrolle" in p for p in problems))



if __name__ == "__main__":
    unittest.main(verbosity=2)
