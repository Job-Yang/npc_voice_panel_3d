#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("render_feishu_failure.py")
SPEC = importlib.util.spec_from_file_location("render_feishu_failure", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FailureSummaryTests(unittest.TestCase):
    def test_prefers_structured_turn_failure_when_final_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "final.txt").write_text("", encoding="utf-8")
            (run_dir / "trae.jsonl").write_text(
                json.dumps(
                    {
                        "type": "turn.failed",
                        "error": {"message": "SSO refresh expired"},
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                MODULE.failure_summary(run_dir),
                "SSO refresh expired",
            )

    def test_falls_back_to_error_then_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "ERROR").write_text("rc=9\n", encoding="utf-8")
            (run_dir / "metrics.json").write_text(
                json.dumps({"agent_rc": 9}),
                encoding="utf-8",
            )
            self.assertEqual(MODULE.failure_summary(run_dir), "rc=9")

            (run_dir / "ERROR").unlink()
            self.assertEqual(MODULE.failure_summary(run_dir), "agent_rc=9")

    def test_render_escapes_failure_text(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "final.txt").write_text("bad <token> & exit", encoding="utf-8")
            xml = MODULE.render(run_dir, "2026-08-13", "stamp", "marker")
            self.assertIn("bad &lt;token&gt; &amp; exit", xml)
            self.assertNotIn("bad <token>", xml)

    def test_supervisor_summary_has_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "supervisor_failure.txt").write_text(
                "creative contract failed",
                encoding="utf-8",
            )
            (run_dir / "final.txt").write_text("agent said done", encoding="utf-8")
            self.assertEqual(
                MODULE.failure_summary(run_dir),
                "creative contract failed",
            )


if __name__ == "__main__":
    unittest.main()
