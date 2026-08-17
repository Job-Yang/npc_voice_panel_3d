#!/usr/bin/env python3
"""Run AutoLoop from a clean daily worktree without touching the control checkout."""

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parent
CONTROL_REPO = Path(
    os.environ.get("AUTOLOOP_CONTROL_REPO", ENGINE_DIR.parent.parent)
).resolve()
REMOTE = os.environ.get("AUTOLOOP_REMOTE", "origin")
BRANCH = os.environ.get("AUTOLOOP_BRANCH", "main")


def round_date():
    return os.environ.get("AUTOLOOP_DATE", dt.date.today().isoformat())


def workspace_root(control_repo):
    override = os.environ.get("AUTOLOOP_WORKSPACE_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    digest = hashlib.sha256(str(control_repo).encode()).hexdigest()[:16]
    return Path.home() / ".local/share/autoloop/workspaces" / digest


def run_git(control_repo, arguments, *, capture=False):
    return subprocess.run(
        ["git", *arguments],
        cwd=control_repo,
        check=False,
        text=True,
        capture_output=capture,
    )


def git_output(control_repo, arguments):
    result = run_git(control_repo, arguments, capture=True)
    if result.returncode:
        raise RuntimeError(
            (result.stderr or result.stdout or "git command failed").strip()
        )
    return result.stdout.strip()


def worktree_branch(date):
    return f"autoloop-run/{date}"


def private_runtime_root(control_repo):
    digest = hashlib.sha256(str(control_repo).encode()).hexdigest()[:16]
    return Path.home() / ".local/state/autoloop" / digest


def prepare_workspace(control_repo, date):
    root = workspace_root(control_repo)
    workspace = root / date
    root.mkdir(parents=True, exist_ok=True)

    fetch = run_git(control_repo, ["fetch", REMOTE, BRANCH])
    if fetch.returncode and not (workspace / ".git").exists():
        raise RuntimeError("fetch failed and no resumable daily workspace exists")

    if (workspace / ".git").exists():
        return workspace
    if workspace.exists():
        raise RuntimeError(f"workspace path exists but is not a git worktree: {workspace}")

    remote_ref = f"{REMOTE}/{BRANCH}"
    branch = worktree_branch(date)
    existing = run_git(
        control_repo,
        ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
    )
    if existing.returncode == 0:
        add = run_git(control_repo, ["worktree", "add", str(workspace), branch])
    else:
        add = run_git(
            control_repo,
            ["worktree", "add", "-b", branch, str(workspace), remote_ref],
        )
    if add.returncode:
        raise RuntimeError(f"failed to create daily worktree: {workspace}")

    metadata = {
        "schema": "AutoLoopWorkspace:v1",
        "date": date,
        "control_repo": str(control_repo),
        "workspace": str(workspace),
        "branch": branch,
        "base_ref": remote_ref,
        "base_commit": git_output(control_repo, ["rev-parse", remote_ref]),
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (root / f"{date}.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return workspace


def notify_workspace_failure(control_repo, date, error):
    root = private_runtime_root(control_repo) / "workspace-failures" / date
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "state.json"
    state = {
        "schema": "AutoLoopWorkspaceFailure:v1",
        "date": date,
        "status": "failed_exhausted",
        "terminal_status": "failed_exhausted",
        "terminal_reason": f"workspace_prepare_failed: {error}",
        "attempts": [],
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    notifier = control_repo / ".autoloop/engine/notify_feishu_failure.py"
    if not notifier.is_file():
        return 1
    return subprocess.run(
        [sys.executable, str(notifier), date, str(state_path), str(root)],
        cwd=control_repo,
        check=False,
    ).returncode


def execute_supervisor(control_repo, date, command):
    workspace = prepare_workspace(control_repo, date)
    supervisor = workspace / ".autoloop/engine/supervisor.py"
    if not supervisor.is_file():
        raise RuntimeError(f"supervisor missing in daily workspace: {supervisor}")
    env = os.environ.copy()
    env.update(
        {
            "AUTOLOOP_DATE": date,
            "AUTOLOOP_CONTROL_REPO": str(control_repo),
            "AUTOLOOP_EXECUTION_WORKSPACE": str(workspace),
        }
    )
    return subprocess.run(
        [sys.executable, str(supervisor), command],
        cwd=workspace,
        env=env,
        check=False,
    ).returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "prewarm", "run", "status"])
    args = parser.parse_args()
    date = round_date()
    try:
        if args.command == "prepare":
            workspace = prepare_workspace(CONTROL_REPO, date)
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "date": date,
                        "control_repo": str(CONTROL_REPO),
                        "workspace": str(workspace),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        return execute_supervisor(CONTROL_REPO, date, args.command)
    except RuntimeError as error:
        notification_rc = notify_workspace_failure(
            CONTROL_REPO,
            date,
            str(error),
        )
        print(
            json.dumps(
                {
                    "status": "workspace_failed",
                    "date": date,
                    "control_repo": str(CONTROL_REPO),
                    "error": str(error),
                    "notification_rc": notification_rc,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 78


if __name__ == "__main__":
    sys.exit(main())
