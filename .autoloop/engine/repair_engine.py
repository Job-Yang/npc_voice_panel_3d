#!/usr/bin/env python3
"""Run one bounded AutoLoop engine repair in an isolated clone."""

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


ENGINE_RELATIVE = Path(".autoloop/engine")
MAX_EVIDENCE_CHARS = 12000


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def sanitize_evidence(text):
    patterns = (
        (r"https?://\S+", "<REDACTED_URL>"),
        (r"\b[\w.+-]+@bytedance\.com\b", "<REDACTED_INTERNAL_EMAIL>"),
        (r"(?:/data00)?/home/[^/\s\"']+", "<REMOTE_HOME>"),
        (r"/Users/[^/\s\"']+", "<LOCAL_HOME>"),
        (
            r"(?i)(access_token|refresh_token|app_secret|authorization)"
            r"([\"'\s:=]+)([^\"'\s,}]+)",
            r"\1\2<REDACTED_SECRET>",
        ),
        (r"\b(?:ou|om|oc|cli)_[0-9a-z]+\b", "<REDACTED_PLATFORM_ID>"),
    )
    value = text[-MAX_EVIDENCE_CHARS:]
    for pattern, replacement in patterns:
        value = re.sub(pattern, replacement, value)
    return value


def git_output(repo, *arguments):
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(
            (result.stderr or result.stdout or "git command failed").strip()
        )
    return result.stdout.strip()


def changed_paths(repo, base):
    committed = git_output(repo, "diff", "--name-only", f"{base}..HEAD")
    working = git_output(repo, "diff", "--name-only", "HEAD")
    untracked = git_output(
        repo,
        "ls-files",
        "--others",
        "--exclude-standard",
    )
    return {
        item
        for group in (committed, working, untracked)
        for item in group.splitlines()
        if item
    }


def validate_paths(paths, repo=None):
    if not paths or not all(
        path == str(ENGINE_RELATIVE)
        or path.startswith(f"{ENGINE_RELATIVE}/")
        for path in paths
    ):
        return False
    if str(ENGINE_RELATIVE / "repair_engine.py") in paths:
        return False
    if not any(
        not Path(path).name.startswith("test_")
        for path in paths
    ):
        return False
    if repo is not None:
        for path in paths:
            target = Path(repo) / path
            if not target.is_file() or target.is_symlink():
                return False
    return True


def validation_commands(repo):
    engine = repo / ENGINE_RELATIVE
    commands = [
        ["bash", "-n", *map(str, sorted(engine.glob("*.sh")))],
        [
            sys.executable,
            "-m",
            "py_compile",
            *map(str, sorted(engine.glob("*.py"))),
        ],
        ["node", "--check", str(engine / "render_feishu_round.js")],
        ["node", "--check", str(engine / "verify_web.js")],
    ]
    commands.extend(
        [sys.executable, str(path)]
        for path in sorted(engine.glob("test_*.py"))
    )
    return commands


def validate_engine(repo, log_path):
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(
        Path.home() / ".cache/autoloop-supervisor/repair-pycache"
    )
    with Path(log_path).open("w", encoding="utf-8") as output:
        for command in validation_commands(repo):
            result = subprocess.run(
                command,
                cwd=repo,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
                text=True,
            )
            if result.returncode:
                return result.returncode
    return 0


def sync_engine(source_repo, execution_repo):
    source = source_repo / ENGINE_RELATIVE
    destination = execution_repo / ENGINE_RELATIVE
    source_files = {
        path.relative_to(source)
        for path in source.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    for path in destination.rglob("*"):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.relative_to(destination) not in source_files
        ):
            path.unlink()
    for relative in source_files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)


def repair(args):
    execution_repo = Path(args.execution_repo).resolve()
    evidence_path = Path(args.evidence).resolve()
    result_path = Path(args.result).resolve()
    private_dir = result_path.parent
    private_dir.mkdir(parents=True, exist_ok=True)
    evidence = sanitize_evidence(
        evidence_path.read_text(encoding="utf-8", errors="replace")
        if evidence_path.exists()
        else "evidence file missing"
    )
    (private_dir / "evidence.redacted.txt").write_text(
        evidence + "\n",
        encoding="utf-8",
    )

    remote = git_output(execution_repo, "remote", "get-url", "origin")
    repair_repo = private_dir / "repo"
    if repair_repo.exists():
        shutil.rmtree(repair_repo)
    clone = subprocess.run(
        [
            "git",
            "clone",
            "--branch",
            "main",
            "--single-branch",
            remote,
            str(repair_repo),
        ],
        cwd=execution_repo,
        check=False,
    )
    if clone.returncode:
        raise RuntimeError("failed to create repair clone")
    base = git_output(repair_repo, "rev-parse", "HEAD")

    prompt = f"""Repair one deterministic AutoLoop engine failure.

Phase: {args.phase}
Failure evidence (already redacted):
--- begin evidence ---
{evidence}
--- end evidence ---

Constraints:
- Modify only files under .autoloop/engine/.
- Do not modify product code, inputs, journal, runs, configuration, images, or credentials.
- Do not commit or push; the supervisor owns publication.
- Reproduce the failure with a focused regression test, make the smallest root-cause fix,
  and run the relevant tests.
- Do not weaken, skip, or delete an existing validation gate.
- Finish with a concise summary of changed files and verification.
"""
    command_override = os.environ.get("AUTOLOOP_REPAIR_COMMAND")
    if command_override:
        command = shlex.split(command_override)
    else:
        trae_cli = os.environ.get(
            "AUTOLOOP_TRAE_CLI",
            str(Path.home() / ".local/bin/trae-cli"),
        )
        command = [
            trae_cli,
            "exec",
            "--permission-mode",
            "custom",
            "--sandbox",
            "workspace-write",
            "--disable",
            "hooks",
            "-c",
            'approval_policy="never"',
            "-c",
            'shell_environment_policy.inherit="all"',
            "-m",
            os.environ.get("AUTOLOOP_MODEL", "gpt-5.5"),
            "-C",
            str(repair_repo),
            prompt,
            "--json",
            "--ephemeral",
            "-o",
            str(private_dir / "repair-final.txt"),
        ]
    env = os.environ.copy()
    env.update(
        {
            "AUTOLOOP_REPAIR_REPO": str(repair_repo),
            "AUTOLOOP_REPAIR_EVIDENCE": str(
                private_dir / "evidence.redacted.txt"
            ),
        }
    )
    with (private_dir / "repair-trace.jsonl").open(
        "w",
        encoding="utf-8",
    ) as output:
        agent = subprocess.run(
            command,
            cwd=repair_repo,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=int(os.environ.get("AUTOLOOP_REPAIR_TIMEOUT", "1200")),
            check=False,
            text=True,
        )
    paths = sorted(changed_paths(repair_repo, base))
    agent_committed = git_output(repair_repo, "rev-parse", "HEAD") != base
    if (
        agent.returncode
        or agent_committed
        or not validate_paths(paths, repair_repo)
    ):
        write_json(
            result_path,
            {
                "status": "rejected",
                "agent_rc": agent.returncode,
                "agent_committed": agent_committed,
                "changed_paths": paths,
                "reason": "agent_failed_or_change_scope_invalid",
            },
        )
        return 1

    validation_rc = validate_engine(
        repair_repo,
        private_dir / "validation.log",
    )
    if validation_rc:
        write_json(
            result_path,
            {
                "status": "rejected",
                "agent_rc": agent.returncode,
                "validation_rc": validation_rc,
                "changed_paths": paths,
                "reason": "validation_failed",
            },
        )
        return validation_rc

    subprocess.run(
        ["git", "add", str(ENGINE_RELATIVE)],
        cwd=repair_repo,
        check=True,
    )
    commit = subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "user.name=AutoLoop Repair",
            "-c",
            "user.email=autoloop-repair@localhost",
            "commit",
            "-m",
            f"fix(autoloop): repair {args.phase} failure",
        ],
        cwd=repair_repo,
        check=False,
    )
    if commit.returncode:
        raise RuntimeError("repair commit failed")
    push = subprocess.run(
        ["git", "push", "origin", "HEAD:main"],
        cwd=repair_repo,
        check=False,
    )
    if push.returncode:
        raise RuntimeError("repair push failed")

    sync_engine(repair_repo, execution_repo)
    commit_sha = git_output(repair_repo, "rev-parse", "HEAD")
    write_json(
        result_path,
        {
            "status": "applied",
            "phase": args.phase,
            "commit": commit_sha,
            "changed_paths": paths,
            "validation_rc": 0,
        },
    )
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--execution-repo", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    try:
        return repair(args)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        write_json(
            args.result,
            {
                "status": "failed",
                "phase": args.phase,
                "reason": str(error),
            },
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
