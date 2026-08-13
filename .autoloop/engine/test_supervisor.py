#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("supervisor.py")
SPEC = importlib.util.spec_from_file_location("autoloop_supervisor", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def base_state():
    return {
        "schema": "AutoLoopSupervisor:v1",
        "date": "2099-01-01",
        "status": "ready",
        "attempts": [],
        "finalize_attempts": 0,
        "prewarm": {"status": "passed"},
    }


class ClassificationTests(unittest.TestCase):
    def test_auth_failure_is_retryable(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "metrics.json").write_text(
                json.dumps({"agent_rc": 1, "preflight_rc": 0}),
                encoding="utf-8",
            )
            (run_dir / "trae.jsonl").write_text(
                "Your ByteDance SSO session could not be refreshed",
                encoding="utf-8",
            )
            self.assertEqual(
                MODULE.classify_attempt(run_dir, 1),
                ("retryable", "agent_transient"),
            )

    def test_creative_contract_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "metrics.json").write_text(
                json.dumps(
                    {
                        "agent_rc": 0,
                        "preflight_rc": 0,
                        "input_validation_rc": 0,
                        "creative_validation_rc": 2,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                MODULE.classify_attempt(run_dir, 2),
                ("nonretryable", "creative_contract"),
            )


class StateMachineTests(unittest.TestCase):
    def test_retry_then_success_uses_one_logical_round(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "2099-01-01_supervisor"
            path = root / "state.json"
            state = base_state()
            attempts = iter(
                [
                    ("retryable", "agent_transient", Path(directory) / "attempt_01"),
                    ("success", "all_gates_passed", Path(directory) / "attempt_02"),
                ]
            )

            def fake_attempt(date, supervisor_root, current):
                classification, reason, run_dir = next(attempts)
                current["attempts"].append(
                    {
                        "number": len(current["attempts"]) + 1,
                        "run_dir": str(run_dir),
                        "classification": classification,
                        "reason": reason,
                    }
                )
                current["final_run_dir"] = str(run_dir)
                return classification, reason, run_dir

            with mock.patch.object(MODULE, "run_attempt", side_effect=fake_attempt), mock.patch.object(
                MODULE, "prewarm", return_value=0
            ), mock.patch.object(MODULE, "finalize", return_value=0) as finalize:
                first = MODULE.run_supervisor("2099-01-01", root, path, state)
                self.assertEqual(first, 75)
                self.assertEqual(state["status"], "retry_wait")

                second = MODULE.run_supervisor("2099-01-01", root, path, state)
                self.assertEqual(second, 0)
                self.assertEqual(state["core_outcome"], "success")
                self.assertEqual(len(state["attempts"]), 2)
                finalize.assert_called_once()

    def test_nonretryable_failure_finalizes_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "2099-01-01_supervisor"
            path = root / "state.json"
            state = base_state()

            def fake_attempt(date, supervisor_root, current):
                run_dir = Path(directory) / "attempt_01"
                current["attempts"].append(
                    {
                        "number": 1,
                        "run_dir": str(run_dir),
                        "classification": "nonretryable",
                        "reason": "creative_contract",
                    }
                )
                current["final_run_dir"] = str(run_dir)
                return "nonretryable", "creative_contract", run_dir

            with mock.patch.object(MODULE, "run_attempt", side_effect=fake_attempt), mock.patch.object(
                MODULE, "finalize", return_value=0
            ) as finalize:
                rc = MODULE.run_supervisor("2099-01-01", root, path, state)
                self.assertEqual(rc, 0)
                self.assertEqual(state["terminal_status"], "failed_nonretryable")
                self.assertEqual(len(state["attempts"]), 1)
                finalize.assert_called_once()

    def test_failed_preflight_does_not_spend_model_smoke(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "2099-01-01_supervisor"
            state = base_state()
            with mock.patch.object(
                MODULE, "run_logged", return_value=(1, 0.1)
            ), mock.patch.object(MODULE, "version_gate") as version_gate:
                rc = MODULE.prewarm("2099-01-01", root, state)
                self.assertEqual(rc, 78)
                self.assertEqual(state["status"], "prewarm_failed")
                version_gate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
