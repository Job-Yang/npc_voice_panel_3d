#!/usr/bin/env python3
import importlib.util
import os
import subprocess
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

            with mock.patch.object(
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


if __name__ == "__main__":
    unittest.main()
