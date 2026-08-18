#!/usr/bin/env python3
"""AutoLoop Supervisor v1: prewarm, classify, retry, resume and finalize one daily round."""

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parent
AUTOLOOP_DIR = ENGINE_DIR.parent
REPO_DIR = AUTOLOOP_DIR.parent
RUNS_DIR = Path(os.environ.get("AUTOLOOP_RUNS_DIR", AUTOLOOP_DIR / "runs"))
MAX_ATTEMPTS = int(os.environ.get("AUTOLOOP_MAX_ATTEMPTS", "3"))
FINAL_STATUSES = {"succeeded", "failed_nonretryable", "failed_exhausted"}
RETRYABLE_PATTERNS = (
    "could not be refreshed",
    "refresh token",
    "timed out",
    "timeout",
    "connection reset",
    "connection refused",
    "temporary failure",
    "network is unreachable",
    "rate limit",
    "too many requests",
    "service unavailable",
    "internal server error",
)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def round_date():
    return os.environ.get("AUTOLOOP_DATE", dt.date.today().isoformat())


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {} if default is None else default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def state_paths(date):
    root = RUNS_DIR / f"{date}_supervisor"
    return root, root / "state.json"


def load_state(date):
    root, path = state_paths(date)
    state = read_json(path, {})
    if not state:
        state = {
            "schema": "AutoLoopSupervisor:v1",
            "date": date,
            "status": "new",
            "attempts": [],
            "finalize_attempts": 0,
            "created_at": now(),
            "updated_at": now(),
        }
    return root, path, state


def save_state(path, state):
    state["updated_at"] = now()
    write_json(path, state)


@contextlib.contextmanager
def supervisor_lock(date):
    digest = hashlib.sha256(str(REPO_DIR).encode()).hexdigest()[:12]
    lock_path = Path(f"/tmp/autoloop-supervisor-{digest}-{date}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("another supervisor process is already running")
        yield


def run_logged(command, log_path, *, env=None, timeout=None, stdin=None):
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8") as output:
        try:
            result = subprocess.run(
                command,
                cwd=REPO_DIR,
                env=env,
                stdin=stdin,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
                text=True,
            )
            return result.returncode, round(time.monotonic() - started, 3)
        except subprocess.TimeoutExpired:
            output.write(f"\n[supervisor] timeout after {timeout}s\n")
            return 124, round(time.monotonic() - started, 3)


def command_override(name, default):
    value = os.environ.get(name)
    return shlex.split(value) if value else default


def static_gate_env():
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(
        Path.home() / ".cache/autoloop-supervisor/pycache"
    )
    return env


def engine_fingerprint():
    digest = hashlib.sha256()
    for path in sorted(ENGINE_DIR.glob("*")):
        if path.is_file() and path.suffix in {".py", ".sh", ".js"}:
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    versions = {}
    for name, command in {
        "trae_cli": [os.environ.get("AUTOLOOP_TRAE_CLI", str(Path.home() / ".local/bin/trae-cli")), "--version"],
        "lark_cli": [os.environ.get("AUTOLOOP_LARK_CLI", str(Path.home() / ".npm-global/bin/lark-cli")), "--version"],
    }.items():
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            versions[name] = (result.stdout or result.stderr).strip()
        except FileNotFoundError:
            versions[name] = f"missing:{command[0]}"
        digest.update(name.encode())
        digest.update(versions[name].encode())
    return digest.hexdigest(), versions


def version_gate(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fingerprint, versions = engine_fingerprint()
    repo_key = hashlib.sha256(str(REPO_DIR).encode()).hexdigest()[:16]
    cache_path = Path.home() / ".cache/autoloop-supervisor" / f"{repo_key}.json"
    cached = read_json(cache_path, {})
    result_path = output_dir / "version_gate.json"
    if cached.get("fingerprint") == fingerprint and cached.get("status") == "passed":
        result = {
            "status": "passed",
            "smoke": "skipped_unchanged",
            "fingerprint": fingerprint,
            "versions": versions,
        }
        write_json(result_path, result)
        return 0, result

    shell_files = sorted(str(path) for path in ENGINE_DIR.glob("*.sh"))
    python_files = sorted(str(path) for path in ENGINE_DIR.glob("*.py"))
    static_commands = [
        ["bash", "-n", *shell_files],
        [sys.executable, "-m", "py_compile", *python_files],
        ["node", "--check", str(ENGINE_DIR / "render_feishu_round.js")],
        ["node", "--check", str(ENGINE_DIR / "verify_web.js")],
        [sys.executable, str(ENGINE_DIR / "test_supervisor.py")],
        [sys.executable, str(ENGINE_DIR / "test_render_feishu_failure.py")],
        [sys.executable, str(ENGINE_DIR / "test_publish_evidence.py")],
        [sys.executable, str(ENGINE_DIR / "test_workspace_runner.py")],
    ]
    static_rc = 0
    static_log = output_dir / "version_static.log"
    with static_log.open("w", encoding="utf-8") as output:
        for command in static_commands:
            result = subprocess.run(
                command,
                cwd=REPO_DIR,
                env=static_gate_env(),
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
                text=True,
            )
            if result.returncode:
                static_rc = result.returncode
                break
    if static_rc:
        result = {
            "status": "failed",
            "stage": "static_gate",
            "static_rc": static_rc,
            "fingerprint": fingerprint,
            "versions": versions,
        }
        write_json(result_path, result)
        return static_rc, result

    if os.environ.get("AUTOLOOP_SKIP_VERSION_SMOKE") == "1":
        smoke_rc = 0
        smoke_result = "skipped_by_environment"
    else:
        trae_cli = os.environ.get(
            "AUTOLOOP_TRAE_CLI", str(Path.home() / ".local/bin/trae-cli")
        )
        final_path = output_dir / "model_smoke_final.txt"
        command = command_override(
            "AUTOLOOP_SMOKE_COMMAND",
            [
                trae_cli,
                "exec",
                "-c",
                'approval_policy="never"',
                "-s",
                "workspace-write",
                "-m",
                os.environ.get("AUTOLOOP_MODEL", "gpt-5.5"),
                "-C",
                str(REPO_DIR),
                "Reply with exactly AUTOLOOP_MODEL_OK",
                "--json",
                "--ephemeral",
                "-o",
                str(final_path),
            ],
        )
        smoke_rc, _ = run_logged(
            command,
            output_dir / "model_smoke.jsonl",
            timeout=180,
            stdin=subprocess.DEVNULL,
        )
        smoke_result = read_text(final_path).strip()
        if smoke_rc == 0 and smoke_result != "AUTOLOOP_MODEL_OK":
            smoke_rc = 65

    result = {
        "status": "passed" if smoke_rc == 0 else "failed",
        "stage": "model_smoke",
        "static_rc": static_rc,
        "smoke": smoke_result,
        "smoke_rc": smoke_rc,
        "fingerprint": fingerprint,
        "versions": versions,
    }
    write_json(result_path, result)
    if smoke_rc == 0 and smoke_result == "AUTOLOOP_MODEL_OK":
        write_json(cache_path, result)
    return smoke_rc, result


def prewarm(date, root, state):
    prewarm_dir = root / "prewarm"
    prewarm_dir.mkdir(parents=True, exist_ok=True)
    output = prewarm_dir / "preflight.json"
    command = command_override(
        "AUTOLOOP_PREFLIGHT_COMMAND",
        ["bash", str(ENGINE_DIR / "preflight.sh"), str(output)],
    )
    rc, duration = run_logged(command, prewarm_dir / "preflight.log", timeout=180)
    if rc == 0:
        gate_rc, gate = version_gate(prewarm_dir)
    else:
        gate_rc, gate = 78, {
            "status": "skipped",
            "reason": "preflight_failed",
        }
    state["prewarm"] = {
        "status": "passed" if rc == 0 and gate_rc == 0 else "failed",
        "preflight_rc": rc,
        "version_gate_rc": gate_rc,
        "duration_seconds": duration,
        "checked_at": now(),
        "details": gate,
    }
    state["status"] = "ready" if rc == 0 and gate_rc == 0 else "prewarm_failed"
    return 0 if state["status"] == "ready" else 78


def classify_attempt(run_dir, returncode):
    run_dir = Path(run_dir)
    metrics = read_json(run_dir / "metrics.json", {})
    sync_failure = read_json(run_dir / "sync_failure.json", {})
    trace = (
        read_text(run_dir / "trae.jsonl")
        + "\n"
        + read_text(run_dir / "final.txt")
        + "\n"
        + read_text(run_dir / "ERROR")
    ).lower()
    if sync_failure or (run_dir / "SKIPPED").exists():
        reason = sync_failure.get("reason") or read_text(run_dir / "SKIPPED") or "unknown"
        return "retryable", f"git_sync_{reason}"
    if returncode == 0:
        return "success", "all_gates_passed"
    if metrics.get("preflight_rc", 0):
        return "retryable", "preflight_infrastructure"
    if metrics.get("agent_rc", 0):
        reason = "agent_transient" if any(p in trace for p in RETRYABLE_PATTERNS) else "agent_process"
        return "retryable", reason
    if metrics.get("visual_verification_rc", 0):
        return "retryable", "visual_infrastructure"
    if metrics.get("input_validation_rc", 0):
        return "nonretryable", "input_contract"
    if metrics.get("creative_validation_rc", 0):
        return "nonretryable", "creative_contract"
    if any(pattern in trace for pattern in RETRYABLE_PATTERNS):
        return "retryable", "transient_runtime"
    return "nonretryable", "unknown_nonretryable"


def run_attempt(date, root, state):
    attempt_number = len(state["attempts"]) + 1
    run_dir = RUNS_DIR / f"{date}_attempt_{attempt_number:02d}"
    previous_reason = (
        state["attempts"][-1].get("reason", "")
        if state["attempts"]
        else ""
    )
    allow_attempt_dirty = (
        attempt_number > 1
        and not previous_reason.startswith("git_sync_")
    )
    env = os.environ.copy()
    env.update(
        {
            "AUTOLOOP_DATE": date,
            "AUTOLOOP_RUN_ID": date,
            "AUTOLOOP_RUN_DIR": str(run_dir),
            "AUTOLOOP_RESUME": "1",
            "AUTOLOOP_DEFER_FINALIZATION": "1",
            "AUTOLOOP_ALLOW_ATTEMPT_DIRTY": "1" if allow_attempt_dirty else "0",
        }
    )
    command = command_override(
        "AUTOLOOP_ITERATE_COMMAND", ["bash", str(ENGINE_DIR / "iterate.sh")]
    )
    state["status"] = "running"
    rc, duration = run_logged(
        command,
        run_dir / "supervisor_attempt.log",
        env=env,
        timeout=int(os.environ.get("AUTOLOOP_ATTEMPT_TIMEOUT", "4500")),
        stdin=subprocess.DEVNULL,
    )
    classification, reason = classify_attempt(run_dir, rc)
    attempt = {
        "number": attempt_number,
        "run_dir": str(run_dir.relative_to(REPO_DIR)),
        "returncode": rc,
        "classification": classification,
        "reason": reason,
        "duration_seconds": duration,
        "finished_at": now(),
    }
    state["attempts"].append(attempt)
    state["final_run_dir"] = str(run_dir.relative_to(REPO_DIR))
    return classification, reason, run_dir


def report_round(date, run_dir, mode):
    env = os.environ.copy()
    env.update({"AUTOLOOP_RUN_ID": date, "AUTOLOOP_REPORT_MODE": mode})
    command = command_override(
        "AUTOLOOP_REPORT_COMMAND",
        ["bash", str(ENGINE_DIR / "report_feishu.sh"), str(run_dir), date],
    )
    return run_logged(
        command,
        Path(run_dir) / "supervisor_report.log",
        env=env,
        timeout=180,
        stdin=subprocess.DEVNULL,
    )[0]


def notify_failure(date, state_path, run_dir):
    command = command_override(
        "AUTOLOOP_NOTIFY_COMMAND",
        [
            sys.executable,
            str(ENGINE_DIR / "notify_feishu_failure.py"),
            date,
            str(state_path),
            str(run_dir),
        ],
    )
    return run_logged(
        command,
        Path(run_dir) / "supervisor_notification.log",
        timeout=90,
        stdin=subprocess.DEVNULL,
    )[0]


def notify_terminal_failure(date, path, state, run_dir, resume_status):
    notify_rc = notify_failure(date, path, run_dir)
    state["notification_rc"] = notify_rc
    if notify_rc:
        state["notification_resume_status"] = resume_status
        state["status"] = "notification_pending"
    else:
        state.pop("notification_resume_status", None)
    save_state(path, state)
    return notify_rc


def archive_round(date, root, state):
    public_root = RUNS_DIR / "public-evidence" / date
    command = [
        sys.executable,
        str(ENGINE_DIR / "publish_evidence.py"),
        "--date",
        date,
        "--supervisor-root",
        str(root),
        "--output",
        str(public_root),
    ]
    for item in state["attempts"]:
        command.extend(
            ["--attempt-dir", str(REPO_DIR / item["run_dir"])]
        )
    publish = subprocess.run(command, cwd=REPO_DIR, check=False)
    if publish.returncode:
        return publish.returncode

    paths = [public_root]
    screenshot = AUTOLOOP_DIR / "journal/assets" / f"{date}-online.png"
    if screenshot.exists():
        paths.append(screenshot)
    subprocess.run(["git", "add", *map(str, paths)], cwd=REPO_DIR, check=False)
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=REPO_DIR, check=False
    )
    if diff.returncode:
        commit = subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "commit",
                "-m",
                f"chore(autoloop): Supervisor 留档 {date}",
            ],
            cwd=REPO_DIR,
            check=False,
        )
        if commit.returncode:
            return commit.returncode
    fetch = subprocess.run(
        ["git", "fetch", "origin", "main"], cwd=REPO_DIR, check=False
    )
    if fetch.returncode:
        return fetch.returncode
    merge = subprocess.run(
        ["git", "merge", "--ff-only", "origin/main"], cwd=REPO_DIR, check=False
    )
    if merge.returncode:
        return merge.returncode
    return subprocess.run(
        ["git", "push", "origin", "HEAD:main"], cwd=REPO_DIR, check=False
    ).returncode


def finalize(date, root, path, state):
    run_dir = REPO_DIR / state["final_run_dir"]
    mode = "success" if state.get("core_outcome") == "success" else "failure"
    if mode == "failure":
        (run_dir / "supervisor_failure.txt").write_text(
            "Supervisor 已完成分类恢复但未能完成本轮："
            f"{state.get('terminal_reason', state.get('terminal_status', 'unknown'))}。"
            f"共执行 {len(state['attempts'])} 个 attempt；详情见 supervisor state.json。\n",
            encoding="utf-8",
        )
    state["finalize_attempts"] = state.get("finalize_attempts", 0) + 1
    report_rc = report_round(date, run_dir, mode)
    state["report_rc"] = report_rc
    if report_rc:
        state["status"] = (
            "failed_exhausted"
            if state["finalize_attempts"] >= MAX_ATTEMPTS
            else "finalization_pending"
        )
        if state["status"] == "failed_exhausted":
            state["terminal_reason"] = "feishu_report_failed"
        save_state(path, state)
        if state["status"] == "failed_exhausted":
            notify_terminal_failure(
                date,
                path,
                state,
                run_dir,
                "failed_exhausted",
            )
        return report_rc

    state["status"] = (
        "succeeded"
        if state.get("core_outcome") == "success"
        else state.get("terminal_status", "failed_exhausted")
    )
    state["completed_at"] = now()
    save_state(path, state)

    if mode == "failure":
        notify_rc = notify_terminal_failure(
            date,
            path,
            state,
            run_dir,
            "finalization_pending",
        )
        if notify_rc:
            return notify_rc

    archive_rc = archive_round(date, root, state)
    if archive_rc:
        state["status"] = (
            "failed_exhausted"
            if state["finalize_attempts"] >= MAX_ATTEMPTS
            else "finalization_pending"
        )
        if state["status"] == "failed_exhausted":
            state["terminal_reason"] = "git_archive_failed"
        state["archive_rc"] = archive_rc
        save_state(path, state)
        if state["status"] == "failed_exhausted":
            notify_terminal_failure(
                date,
                path,
                state,
                run_dir,
                "failed_exhausted",
            )
    return archive_rc


def run_supervisor(date, root, path, state):
    if state["status"] in FINAL_STATUSES:
        print(json.dumps(state, ensure_ascii=False))
        return 0 if state["status"] == "succeeded" else 1
    if state["status"] == "notification_pending":
        run_dir = REPO_DIR / state["final_run_dir"]
        notify_rc = notify_failure(date, path, run_dir)
        state["notification_rc"] = notify_rc
        if notify_rc:
            save_state(path, state)
            return notify_rc
        resume_status = state.pop(
            "notification_resume_status",
            "failed_exhausted",
        )
        state["status"] = resume_status
        save_state(path, state)
        if resume_status == "finalization_pending":
            return finalize(date, root, path, state)
        return 1
    if state["status"] == "finalization_pending":
        return finalize(date, root, path, state)

    if state["status"] == "retry_wait" or state.get("prewarm", {}).get("status") != "passed":
        prewarm_rc = prewarm(date, root, state)
        save_state(path, state)
        if prewarm_rc:
            state["prewarm_failures"] = state.get("prewarm_failures", 0) + 1
            if state["prewarm_failures"] >= MAX_ATTEMPTS:
                state["core_outcome"] = "failure"
                state["terminal_status"] = "failed_exhausted"
                state["terminal_reason"] = "prewarm_infrastructure"
                synthetic = RUNS_DIR / f"{date}_attempt_01"
                synthetic.mkdir(parents=True, exist_ok=True)
                (synthetic / "final.txt").write_text(
                    "Supervisor 预热连续失败，未启动 Agent。详情见 supervisor/prewarm。\n",
                    encoding="utf-8",
                )
                state["attempts"].append(
                    {
                        "number": 1,
                        "run_dir": str(synthetic.relative_to(REPO_DIR)),
                        "returncode": prewarm_rc,
                        "classification": "retryable",
                        "reason": "prewarm_infrastructure",
                        "finished_at": now(),
                    }
                )
                state["final_run_dir"] = str(synthetic.relative_to(REPO_DIR))
                save_state(path, state)
                return finalize(date, root, path, state)
            state["status"] = "retry_wait"
            save_state(path, state)
            return prewarm_rc

    classification, reason, run_dir = run_attempt(date, root, state)
    if classification == "success":
        state["core_outcome"] = "success"
        state["terminal_status"] = "succeeded"
        save_state(path, state)
        return finalize(date, root, path, state)
    if classification == "nonretryable":
        state["core_outcome"] = "failure"
        state["terminal_status"] = "failed_nonretryable"
        state["terminal_reason"] = reason
        save_state(path, state)
        return finalize(date, root, path, state)
    if len(state["attempts"]) >= MAX_ATTEMPTS:
        state["core_outcome"] = "failure"
        state["terminal_status"] = "failed_exhausted"
        state["terminal_reason"] = reason
        save_state(path, state)
        return finalize(date, root, path, state)
    state["status"] = "retry_wait"
    state["next_reason"] = reason
    save_state(path, state)
    return 75


def resume_previous_notifications(current_date):
    for path in sorted(RUNS_DIR.glob("*_supervisor/state.json")):
        root = path.parent
        date = root.name.removesuffix("_supervisor")
        if date >= current_date:
            continue
        state = read_json(path, {})
        if state.get("status") != "notification_pending":
            continue
        try:
            with supervisor_lock(date):
                state = read_json(path, state)
                if state.get("status") == "notification_pending":
                    run_supervisor(date, root, path, state)
        except SystemExit:
            continue


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prewarm", "run", "status"])
    args = parser.parse_args()
    date = round_date()
    if args.command != "status":
        resume_previous_notifications(date)
    root, path, state = load_state(date)
    root.mkdir(parents=True, exist_ok=True)
    with supervisor_lock(date):
        if args.command == "status":
            print(json.dumps(state, ensure_ascii=False, indent=2))
            return 0
        if args.command == "prewarm":
            rc = prewarm(date, root, state)
            save_state(path, state)
        else:
            rc = run_supervisor(date, root, path, state)
        print(json.dumps(read_json(path, state), ensure_ascii=False, indent=2))
        return rc


if __name__ == "__main__":
    sys.exit(main())
