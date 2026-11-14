#!/usr/bin/env python3
"""Tests für scripts/check_docs.py — veraltete Aktualitätsbehauptungen finden.

Die historischen Korrekturabschnitte sollen bleiben dürfen. Was nicht bleiben
darf, ist ein Satz, der heute noch „maßgeblich", „offen" oder „nicht
implementiert" behauptet, obwohl Code und Messung etwas anderes sagen.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))

import check_docs  # noqa: E402


class TestDocConsistency(unittest.TestCase):

    def test_repository_checks_pass(self):
        root = Path(PROJECT_DIR)
        self.assertEqual(check_docs.run_checks(root), [])
        # Der Sweep deckt nicht nur die SSOT ab, sondern auch README,
        # Forensik-Audits, Prototypen und den CI-Workflow.
        for relative in ("README.md", "docs/LFM25_AUDIO_AUDIT.md",
                         "docs/LFM25_AUDIO_AUDIT_V2.md",
                         "PROTOTYPEN/README.md",
                         ".github/workflows/state-consistency.yml"):
            self.assertIn(relative, check_docs.CURRENT_FILES)
            self.assertIn(relative, check_docs.required_phrases(311, 19, root))
        self.assertEqual(len(check_docs.CURRENT_FILES), 13)

    def test_forbidden_current_phrase_is_detected(self):
        hits = check_docs.forbidden_in(
            "Wir haben **136\nTestfunktionen in 9 Suiten** und keine MUSCAL-Schichten. "
            "Voraussetzung: Backend läuft. ## Phasenplan")
        self.assertTrue(any("136 Testfunktionen" in h for h in hits))
        self.assertTrue(any("MUSCAL-Schichten" in h for h in hits))
        self.assertTrue(any("Voraussetzung: Backend" in h for h in hits))
        self.assertTrue(any("## Phasenplan" in h for h in hits))

    def test_required_phrase_missing_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "GUIALITA_STATE.yaml").write_text(
                "  test_functions_total: 311\n  suites: 19\n", encoding="utf-8")
            for relative in check_docs.required_phrases(311, 19, root):
                if relative == "docs/GUIALITA_STATE.yaml":
                    continue  # Zahlen müssen lesbar bleiben, Rest fehlt
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            problems = check_docs.check_required_phrases(root)
            self.assertTrue(problems)
            self.assertTrue(any("aktuelle Formulierung fehlt" in p for p in problems))
            self.assertTrue(any("README.md" in p for p in problems))
            self.assertTrue(any("LFM25_AUDIO_AUDIT" in p for p in problems))

    def test_required_phrases_pass_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            phrases = check_docs.required_phrases(311, 19, root)
            for relative, needles in phrases.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                prefix = "  test_functions_total: 311\n  suites: 19\n" \
                    if relative == "docs/GUIALITA_STATE.yaml" else ""
                path.write_text(prefix + "\n".join(needles), encoding="utf-8")
            self.assertEqual(check_docs.check_required_phrases(root), [])

    def test_ssot_invariants_are_present(self):
        self.assertEqual(check_docs.check_invariants(Path(PROJECT_DIR)), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
