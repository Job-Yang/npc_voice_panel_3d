#!/usr/bin/env python3
import importlib.util
import json
import shutil
import subprocess
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
    def test_git_sync_skip_is_retryable_even_with_zero_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "sync_failure.json").write_text(
                json.dumps(
                    {"stage": "git_sync", "reason": "dirty_worktree"}
                ),
                encoding="utf-8",
            )
            (run_dir / "SKIPPED").write_text(
                "dirty_worktree\n",
                encoding="utf-8",
            )
            self.assertEqual(
                MODULE.classify_attempt(run_dir, 0),
                ("retryable", "git_sync_dirty_worktree"),
            )

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
    def test_static_gate_python_cache_is_outside_repository(self):
        cache_prefix = Path(MODULE.static_gate_env()["PYTHONPYCACHEPREFIX"])
        self.assertFalse(cache_prefix.is_relative_to(MODULE.REPO_DIR))

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

    def test_git_sync_retry_does_not_allow_dirty_resume(self):
        state = base_state()
        state["attempts"] = [
            {
                "number": 1,
                "run_dir": ".autoloop/runs/attempt_01",
                "classification": "retryable",
                "reason": "git_sync_dirty_worktree",
            }
        ]
        captured = {}

        def fake_run_logged(command, log_path, **kwargs):
            captured.update(kwargs["env"])
            return 79, 0.1

        with mock.patch.object(
            MODULE, "run_logged", side_effect=fake_run_logged
        ), mock.patch.object(
            MODULE,
            "classify_attempt",
            return_value=("retryable", "git_sync_dirty_worktree"),
        ):
            MODULE.run_attempt("2099-01-01", Path("."), state)

        self.assertEqual(captured["AUTOLOOP_ALLOW_ATTEMPT_DIRTY"], "0")

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

    def test_terminal_failure_requires_verified_notification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "2099-01-01_supervisor"
            path = root / "state.json"
            run_dir = Path(directory) / "attempt_01"
            run_dir.mkdir(parents=True)
            state = base_state()
            state.update(
                {
                    "core_outcome": "failure",
                    "terminal_status": "failed_exhausted",
                    "terminal_reason": "git_sync_dirty_worktree",
                    "final_run_dir": str(run_dir),
                    "attempts": [{"run_dir": str(run_dir)}],
                }
            )

            with mock.patch.object(MODULE, "report_round", return_value=0), mock.patch.object(
                MODULE, "notify_failure", return_value=1
            ), mock.patch.object(MODULE, "archive_round") as archive:
                rc = MODULE.finalize("2099-01-01", root, path, state)

            self.assertEqual(rc, 1)
            self.assertEqual(state["status"], "notification_pending")
            self.assertEqual(state["notification_rc"], 1)
            archive.assert_not_called()

    def test_exhausted_report_failure_notifies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "2099-01-01_supervisor"
            path = root / "state.json"
            run_dir = Path(directory) / "attempt_01"
            run_dir.mkdir(parents=True)
            state = base_state()
            state.update(
                {
                    "core_outcome": "success",
                    "terminal_status": "succeeded",
                    "final_run_dir": str(run_dir),
                    "attempts": [{"run_dir": str(run_dir)}],
                    "finalize_attempts": MODULE.MAX_ATTEMPTS - 1,
                }
            )

            with mock.patch.object(MODULE, "report_round", return_value=1), mock.patch.object(
                MODULE, "notify_failure", return_value=0
            ) as notify:
                rc = MODULE.finalize("2099-01-01", root, path, state)

            self.assertEqual(rc, 1)
            self.assertEqual(state["status"], "partial_success")
            self.assertEqual(state["user_outcome"], "partial_success")
            self.assertEqual(state["terminal_reason"], "feishu_report_failed")
            notify.assert_called_once()

    def test_pending_notification_resumes_after_verified_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "2099-01-01_supervisor"
            path = root / "state.json"
            run_dir = Path(directory) / "attempt_01"
            run_dir.mkdir(parents=True)
            state = base_state()
            state.update(
                {
                    "status": "notification_pending",
                    "notification_resume_status": "failed_exhausted",
                    "final_run_dir": str(run_dir),
                }
            )

            with mock.patch.object(MODULE, "notify_failure", return_value=0):
                rc = MODULE.run_supervisor(
                    "2099-01-01",
                    root,
                    path,
                    state,
                )

            self.assertEqual(rc, 1)
            self.assertEqual(state["status"], "failed_exhausted")
            self.assertEqual(state["notification_rc"], 0)

    def test_exhausted_archive_failure_is_partial_and_remains_recoverable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "2099-01-01_supervisor"
            path = root / "state.json"
            run_dir = Path(directory) / "attempt_01"
            run_dir.mkdir(parents=True)
            state = base_state()
            state.update(
                {
                    "core_outcome": "success",
                    "terminal_status": "succeeded",
                    "final_run_dir": str(run_dir),
                    "attempts": [{"run_dir": str(run_dir)}],
                    "finalize_attempts": MODULE.MAX_ATTEMPTS - 1,
                }
            )

            with mock.patch.object(
                MODULE,
                "report_round",
                return_value=0,
            ), mock.patch.object(
                MODULE,
                "archive_round",
                return_value=128,
            ), mock.patch.object(
                MODULE,
                "notify_failure",
                return_value=0,
            ):
                rc = MODULE.finalize("2099-01-01", root, path, state)

            self.assertEqual(rc, 128)
            self.assertEqual(state["status"], "partial_success")
            self.assertEqual(state["user_outcome"], "partial_success")
            self.assertEqual(state["terminal_reason"], "git_archive_failed")

            archived_state = {}

            def successful_archive(date, supervisor_root, current):
                archived_state.update(current)
                return 0

            with mock.patch.object(
                MODULE,
                "report_round",
                return_value=0,
            ), mock.patch.object(
                MODULE,
                "archive_round",
                side_effect=successful_archive,
            ), mock.patch.object(
                MODULE,
                "notify_failure",
                return_value=0,
            ):
                rc = MODULE.run_supervisor("2099-01-01", root, path, state)

            self.assertEqual(rc, 0)
            self.assertEqual(state["status"], "succeeded")
            self.assertEqual(state["user_outcome"], "success")
            self.assertEqual(state["archive_rc"], 0)
            self.assertNotIn("terminal_reason", state)
            self.assertEqual(state["recovered_from"], "git_archive_failed")
            self.assertEqual(archived_state["archive_rc"], 0)
            self.assertEqual(
                archived_state["recovered_from"],
                "git_archive_failed",
            )

    def test_legacy_exhausted_finalization_is_migrated_and_recovered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "2099-01-01_supervisor"
            path = root / "state.json"
            run_dir = Path(directory) / "attempt_01"
            run_dir.mkdir(parents=True)
            state = base_state()
            state.update(
                {
                    "status": "failed_exhausted",
                    "core_outcome": "success",
                    "terminal_status": "succeeded",
                    "terminal_reason": "git_archive_failed",
                    "archive_rc": 128,
                    "final_run_dir": str(run_dir),
                    "attempts": [{"run_dir": str(run_dir)}],
                }
            )

            with mock.patch.object(
                MODULE,
                "report_round",
                return_value=0,
            ), mock.patch.object(
                MODULE,
                "archive_round",
                return_value=0,
            ), mock.patch.object(
                MODULE,
                "notify_failure",
                return_value=0,
            ):
                rc = MODULE.run_supervisor("2099-01-01", root, path, state)

            self.assertEqual(rc, 0)
            self.assertEqual(state["status"], "succeeded")
            self.assertEqual(state["user_outcome"], "success")
            self.assertEqual(state["recovered_from"], "git_archive_failed")

    def test_failed_recovery_notification_is_retried_without_rerunning_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "2099-01-01_supervisor"
            path = root / "state.json"
            run_dir = Path(directory) / "attempt_01"
            run_dir.mkdir(parents=True)
            state = base_state()
            state.update(
                {
                    "status": "partial_success",
                    "core_outcome": "success",
                    "user_outcome": "partial_success",
                    "terminal_status": "succeeded",
                    "terminal_reason": "git_archive_failed",
                    "final_run_dir": str(run_dir),
                    "attempts": [{"run_dir": str(run_dir)}],
                }
            )

            with mock.patch.object(
                MODULE,
                "report_round",
                return_value=0,
            ), mock.patch.object(
                MODULE,
                "archive_round",
                return_value=0,
            ), mock.patch.object(
                MODULE,
                "notify_failure",
                return_value=1,
            ):
                rc = MODULE.run_supervisor("2099-01-01", root, path, state)

            self.assertEqual(rc, 1)
            self.assertEqual(state["status"], "notification_pending")
            self.assertEqual(
                state["notification_resume_status"],
                "succeeded",
            )

            with mock.patch.object(
                MODULE,
                "notify_failure",
                return_value=0,
            ), mock.patch.object(MODULE, "run_attempt") as attempt:
                rc = MODULE.run_supervisor("2099-01-01", root, path, state)

            self.assertEqual(rc, 0)
            self.assertEqual(state["status"], "succeeded")
            attempt.assert_not_called()

    def test_archive_uses_fresh_remote_base_despite_diverged_execution_clone(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            seed = root / "seed"
            repo = root / "execution"

            subprocess.run(["git", "init", "--bare", str(remote)], check=True)
            subprocess.run(
                ["git", "init", "-b", "main", str(seed)],
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=seed,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=seed,
                check=True,
            )
            (seed / "base.txt").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=seed, check=True)
            subprocess.run(
                ["git", "commit", "-m", "base"],
                cwd=seed,
                check=True,
            )
            subprocess.run(
                ["git", "remote", "add", "origin", str(remote)],
                cwd=seed,
                check=True,
            )
            subprocess.run(
                ["git", "push", "-u", "origin", "main"],
                cwd=seed,
                check=True,
            )
            subprocess.run(
                ["git", "clone", "-b", "main", str(remote), str(repo)],
                check=True,
            )

            (seed / "remote.txt").write_text("remote\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=seed, check=True)
            subprocess.run(
                ["git", "commit", "-m", "remote advance"],
                cwd=seed,
                check=True,
            )
            subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=seed,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo,
                check=True,
            )
            (repo / "local.txt").write_text("local\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "local divergence"],
                cwd=repo,
                check=True,
            )
            (repo / "private.txt").write_text("keep private\n", encoding="utf-8")

            auto = repo / ".autoloop"
            engine = auto / "engine"
            runs = auto / "runs"
            supervisor_root = runs / "2099-01-01_supervisor"
            attempt = runs / "2099-01-01_attempt_01"
            engine.mkdir(parents=True)
            supervisor_root.mkdir(parents=True)
            attempt.mkdir(parents=True)
            shutil.copy2(
                Path(__file__).with_name("publish_evidence.py"),
                engine / "publish_evidence.py",
            )
            screenshot = auto / "journal/assets/2099-01-01-online.png"
            screenshot.parent.mkdir(parents=True)
            screenshot.write_bytes(b"unscanned screenshot")
            (supervisor_root / "state.json").write_text(
                json.dumps(
                    {
                        "schema": "AutoLoopSupervisor:v1",
                        "date": "2099-01-01",
                        "status": "succeeded",
                        "core_outcome": "success",
                    }
                ),
                encoding="utf-8",
            )
            (attempt / "metrics.json").write_text(
                '{"agent_rc": 0}\n',
                encoding="utf-8",
            )

            with mock.patch.object(MODULE, "REPO_DIR", repo), mock.patch.object(
                MODULE, "AUTOLOOP_DIR", auto
            ), mock.patch.object(MODULE, "RUNS_DIR", runs), mock.patch.object(
                MODULE, "ENGINE_DIR", engine
            ):
                rc = MODULE.archive_round(
                    "2099-01-01",
                    supervisor_root,
                    {
                        "attempts": [
                            {
                                "run_dir": ".autoloop/runs/2099-01-01_attempt_01"
                            }
                        ]
                    },
                )

            self.assertEqual(rc, 0)
            archived = subprocess.run(
                [
                    "git",
                    "--git-dir",
                    str(remote),
                    "show",
                    "main:.autoloop/runs/public-evidence/2099-01-01/state.json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "succeeded"', archived.stdout)
            screenshot_check = subprocess.run(
                [
                    "git",
                    "--git-dir",
                    str(remote),
                    "cat-file",
                    "-e",
                    "main:.autoloop/journal/assets/2099-01-01-online.png",
                ],
                check=False,
            )
            self.assertNotEqual(screenshot_check.returncode, 0)
            self.assertTrue((repo / "private.txt").exists())


if __name__ == "__main__":
    unittest.main()
