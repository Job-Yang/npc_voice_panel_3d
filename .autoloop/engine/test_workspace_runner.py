#!/usr/bin/env python3
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("workspace_runner.py")
SPEC = importlib.util.spec_from_file_location("workspace_runner", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def git(cwd, *arguments):
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class WorkspaceRunnerTests(unittest.TestCase):
    def test_dirty_diverged_control_checkout_does_not_enter_daily_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            seed = root / "seed"
            control = root / "control"
            workspaces = root / "workspaces"

            git(root, "init", "--bare", str(remote))
            git(root, "init", "-b", "main", str(seed))
            git(seed, "config", "user.name", "AutoLoop Test")
            git(seed, "config", "user.email", "autoloop@example.com")
            (seed / "tracked.txt").write_text("remote\n", encoding="utf-8")
            git(seed, "add", "tracked.txt")
            git(seed, "commit", "-m", "remote base")
            git(seed, "remote", "add", "origin", str(remote))
            git(seed, "push", "-u", "origin", "main")

            git(root, "clone", "-b", "main", str(remote), str(control))
            git(control, "config", "user.name", "AutoLoop Test")
            git(control, "config", "user.email", "autoloop@example.com")
            (control / "local-commit.txt").write_text(
                "control-only commit\n",
                encoding="utf-8",
            )
            git(control, "add", "local-commit.txt")
            git(control, "commit", "-m", "local divergence")
            (control / "tracked.txt").write_text(
                "private dirty change\n",
                encoding="utf-8",
            )
            (control / "private-note.txt").write_text(
                "must stay private\n",
                encoding="utf-8",
            )

            before_tracked = (control / "tracked.txt").read_bytes()
            before_private = (control / "private-note.txt").read_bytes()
            with mock.patch.dict(
                os.environ,
                {"AUTOLOOP_WORKSPACE_ROOT": str(workspaces)},
            ):
                workspace = MODULE.prepare_workspace(control, "2099-01-01")

            self.assertEqual(
                (workspace / "tracked.txt").read_text(encoding="utf-8"),
                "remote\n",
            )
            self.assertFalse((workspace / "private-note.txt").exists())
            self.assertFalse((workspace / "local-commit.txt").exists())
            self.assertEqual((control / "tracked.txt").read_bytes(), before_tracked)
            self.assertEqual(
                (control / "private-note.txt").read_bytes(),
                before_private,
            )
            self.assertEqual(
                git(workspace, "rev-parse", "HEAD"),
                git(control, "rev-parse", "origin/main"),
            )

    def test_same_date_reuses_workspace_for_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            control = root / "control"
            workspaces = root / "workspaces"

            git(root, "init", "--bare", str(remote))
            git(root, "init", "-b", "main", str(control))
            git(control, "config", "user.name", "AutoLoop Test")
            git(control, "config", "user.email", "autoloop@example.com")
            (control / "tracked.txt").write_text("base\n", encoding="utf-8")
            git(control, "add", "tracked.txt")
            git(control, "commit", "-m", "base")
            git(control, "remote", "add", "origin", str(remote))
            git(control, "push", "-u", "origin", "main")

            with mock.patch.dict(
                os.environ,
                {"AUTOLOOP_WORKSPACE_ROOT": str(workspaces)},
            ):
                first = MODULE.prepare_workspace(control, "2099-01-01")
                (first / "partial.txt").write_text("resume me\n", encoding="utf-8")
                second = MODULE.prepare_workspace(control, "2099-01-01")

            self.assertEqual(first, second)
            self.assertEqual(
                (second / "partial.txt").read_text(encoding="utf-8"),
                "resume me\n",
            )

    def test_workspace_failure_uses_existing_notification_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = root / "control"
            notifier = control / ".autoloop/engine/notify_feishu_failure.py"
            notifier.parent.mkdir(parents=True)
            notifier.write_text("# placeholder\n", encoding="utf-8")
            captured = {}

            def fake_run(command, **kwargs):
                captured["command"] = command
                return subprocess.CompletedProcess(command, 0)

            with mock.patch.dict(
                os.environ,
                {},
                clear=True,
            ), mock.patch.object(
                MODULE,
                "private_runtime_root",
                return_value=root / "runtime",
            ), mock.patch.object(subprocess, "run", side_effect=fake_run):
                rc = MODULE.notify_workspace_failure(
                    control,
                    "2099-01-01",
                    "fetch unavailable",
                )

            self.assertEqual(rc, 0)
            state = (
                root
                / "runtime/workspace-failures/2099-01-01/state.json"
            ).read_text(encoding="utf-8")
            self.assertIn("workspace_prepare_failed", state)
            self.assertIn(str(notifier), captured["command"])

    def test_os_workspace_error_is_reported_and_notified(self):
        with mock.patch.object(
            MODULE,
            "prepare_workspace",
            side_effect=PermissionError("workspace denied"),
        ), mock.patch.object(
            MODULE,
            "notify_workspace_failure",
            return_value=0,
        ) as notify:
            with mock.patch.object(
                sys,
                "argv",
                ["workspace_runner.py", "prepare"],
            ):
                rc = MODULE.main()

        self.assertEqual(rc, 78)
        notify.assert_called_once()

    def test_previous_day_pending_state_is_resumed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old_workspace = root / "2099-01-01"
            state_path = (
                old_workspace
                / ".autoloop/runs/2099-01-01_supervisor/state.json"
            )
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps({"status": "notification_pending"}),
                encoding="utf-8",
            )

            with mock.patch.object(
                MODULE,
                "workspace_root",
                return_value=root,
            ), mock.patch.object(MODULE, "supervisor_process", return_value=0) as run:
                MODULE.resume_incomplete_workspaces(
                    root / "control",
                    "2099-01-02",
                )

            run.assert_called_once_with(
                root / "control",
                old_workspace,
                "2099-01-01",
                "run",
            )

    def test_external_launcher_loads_latest_runner_from_remote(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            seed = root / "seed"
            control = root / "control"
            home = root / "home"
            external_launcher = root / "workspace_launcher.sh"

            git(root, "init", "--bare", str(remote))
            git(root, "init", "-b", "main", str(seed))
            git(seed, "config", "user.name", "AutoLoop Test")
            git(seed, "config", "user.email", "autoloop@example.com")
            engine = seed / ".autoloop/engine"
            engine.mkdir(parents=True)
            external_launcher.write_bytes(
                MODULE_PATH.with_name("workspace_launcher.sh").read_bytes()
            )
            (engine / "workspace_launcher.sh").write_bytes(
                external_launcher.read_bytes()
            )
            (engine / "workspace_runner.py").write_text(
                'print("runner-v1")\n',
                encoding="utf-8",
            )
            git(seed, "add", ".")
            git(seed, "commit", "-m", "runner v1")
            git(seed, "remote", "add", "origin", str(remote))
            git(seed, "push", "-u", "origin", "main")
            git(root, "clone", "-b", "main", str(remote), str(control))

            (engine / "workspace_runner.py").write_text(
                'print("runner-v2")\n',
                encoding="utf-8",
            )
            git(seed, "add", ".")
            git(seed, "commit", "-m", "runner v2")
            git(seed, "push", "origin", "main")
            (control / "private.txt").write_text("dirty\n", encoding="utf-8")
            external_launcher.chmod(0o755)

            result = subprocess.run(
                [str(external_launcher), str(control), "prepare"],
                env={**os.environ, "HOME": str(home)},
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("runner-v2", result.stdout)
            self.assertTrue((control / "private.txt").exists())


if __name__ == "__main__":
    unittest.main()
