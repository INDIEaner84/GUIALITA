#!/usr/bin/env python3
"""Tests für scripts/benchmark.py — Statistik ohne Server, ohne Modelle.

Warum: Die Benchmark-Zahlen sind ab ADR-002 (P2) Entscheidungsgrundlage für
Modellwahl und Rollen. Ein still falsches Perzentil würde jede dieser
Entscheidungen verzerren, ohne irgendwo aufzufallen. Deshalb prüft diese Suite
die Rechenwege, nicht die Messwerte.

Läuft ohne Backend, ohne GPU, ohne Modell — nur Standardbibliothek.
"""
import os
import sys
import unittest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))

import benchmark  # noqa: E402


class TestPercentile(unittest.TestCase):
    """Nearest-Rank: es wird nie ein Wert interpoliert, den niemand gemessen hat."""

    def test_single_value(self):
        self.assertEqual(benchmark.percentile([42.0], 0.95), 42.0)

    def test_median_rank(self):
        # 1..10, p50 -> Rang 5 -> Wert 5.0
        self.assertEqual(benchmark.percentile([float(v) for v in range(1, 11)], 0.5), 5.0)

    def test_p95_never_exceeds_max(self):
        values = [float(v) for v in range(1, 21)]
        self.assertEqual(benchmark.percentile(values, 0.95), 19.0)
        self.assertLessEqual(benchmark.percentile(values, 1.0), max(values))

    def test_empty(self):
        self.assertEqual(benchmark.percentile([], 0.95), 0.0)


class TestStats(unittest.TestCase):

    def test_reports_count_and_bounds(self):
        result = benchmark.stats([10.0, 20.0, 30.0])
        self.assertEqual(result["n"], 3)
        self.assertEqual(result["min_ms"], 10.0)
        self.assertEqual(result["max_ms"], 30.0)
        self.assertEqual(result["median_ms"], 20.0)

    def test_p95_between_median_and_max(self):
        result = benchmark.stats([5.0, 100.0, 7.0, 9.0, 11.0])
        self.assertGreaterEqual(result["p95_ms"], result["median_ms"])
        self.assertLessEqual(result["p95_ms"], result["max_ms"])

    def test_empty_is_not_a_zero_measurement(self):
        # n=0 muss unterscheidbar bleiben von "gemessen und 0 ms".
        result = benchmark.stats([])
        self.assertEqual(result, {"n": 0})
        self.assertNotIn("median_ms", result)

    def test_accepts_ints(self):
        result = benchmark.stats([1, 2, 3])
        self.assertEqual(result["n"], 3)
        self.assertIsInstance(result["median_ms"], float)


class TestFormatting(unittest.TestCase):

    def test_none_is_not_zero(self):
        # Eine fehlende Messung darf nicht als "0.0" erscheinen.
        self.assertEqual(benchmark.fmt(None), "—")

    def test_float_is_rounded_to_one_decimal(self):
        self.assertEqual(benchmark.fmt(12.3456), "12.3")


if __name__ == "__main__":
    unittest.main(verbosity=2)
