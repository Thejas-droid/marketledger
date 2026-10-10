"""Checks for the offline report and clean source publication package."""
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


report = module("report")
export = module("export")


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.simulation = json.loads((ROOT / "examples/expected_simulation.json").read_text(encoding="utf-8"))
        self.analysis = json.loads((ROOT / "examples/expected_arbitrage.json").read_text(encoding="utf-8"))

    def test_report_is_offline_and_has_accessible_controls(self):
        content = report.render(self.simulation, self.analysis)
        HTMLParser().feed(content)
        self.assertNotIn("__REPORT_DATA__", content)
        self.assertNotIn('<script src=', content)
        self.assertNotIn('<link ', content)
        self.assertNotIn('https://', content)
        self.assertIn('aria-label="Filter executions"', content)
        self.assertIn('aria-live="polite"', content)
        self.assertIn('lang="en"', content)

    def test_embedded_data_cannot_close_script(self):
        content = report.render({"broker": "</script><script>alert(1)</script>&"}, {})
        self.assertNotIn("<script>alert(1)", content)
        self.assertIn("\\u003c/script\\u003e", content)

    def test_large_integer_is_rejected_without_rounding(self):
        with self.assertRaisesRegex(ValueError, "precision"):
            report.render({"turnover_cents": 9007199254740992}, {})

    @unittest.skipUnless(shutil.which("node"), "Node is optional; needed only for report JavaScript checks")
    def test_report_javascript(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.html"
            path.write_text(report.render(self.simulation, self.analysis), encoding="utf-8")
            result = subprocess.run(["node", str(ROOT / "tests/report_ui.cjs"), str(path)],
                                    capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


class ExportTests(unittest.TestCase):
    def test_release_allowlist(self):
        paths = export.collect_files(ROOT)
        names = {p.relative_to(ROOT).as_posix() for p in paths}
        self.assertIn("LICENSE", names)
        self.assertIn("THIRD_PARTY_NOTICES.md", names)
        self.assertIn(".github/workflows/ci.yml", names)
        self.assertIn("src/engine.cpp", names)
        self.assertFalse(any(n.startswith((".legacy/", "build/", "release/", ".git/")) for n in names))
        self.assertFalse(any("__pycache__" in n for n in names))

    def test_release_credential_check(self):
        self.assertIsNotNone(export.TOKEN.search(b"ghp_" + b"x" * 36))
        self.assertIsNotNone(export.TOKEN.search(b"AKIA" + b"A" * 16))


if __name__ == "__main__":
    unittest.main(verbosity=2)
