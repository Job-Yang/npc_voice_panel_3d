#!/usr/bin/env python3
"""Send and verify one idempotent AutoLoop failure notification."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parent
AUTOLOOP_DIR = ENGINE_DIR.parent
REPO_DIR = AUTOLOOP_DIR.parent


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {} if default is None else default


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def find_lark_cli():
    override = os.environ.get("AUTOLOOP_LARK_CLI")
    candidates = [
        override,
        shutil.which("lark-cli"),
        str(Path.home() / ".npm-global/bin/lark-cli"),
        str(Path.home() / ".local/bin/lark-cli"),
    ]
    return next((item for item in candidates if item and Path(item).is_file()), "")


def run_json(command):
    env = os.environ.copy()
    env["LARKSUITE_CLI_NO_UPDATE_NOTIFIER"] = "1"
    env["LARKSUITE_CLI_NO_SKILLS_NOTIFIER"] = "1"
    result = subprocess.run(
        command,
        cwd=REPO_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    payload = {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        pass
    return result.returncode, payload, (result.stderr or result.stdout).strip()


def nested_value(value, key):
    if isinstance(value, dict):
        if value.get(key):
            return value[key]
        for child in value.values():
            found = nested_value(child, key)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = nested_value(child, key)
            if found:
                return found
    return ""


def dirty_paths(run_dir):
    run_dir = Path(run_dir)
    repo_key = hashlib.sha256(str(REPO_DIR).encode()).hexdigest()[:16]
    private_root = Path(
        os.environ.get(
            "AUTOLOOP_PRIVATE_STATE_DIR",
            str(Path.home() / ".local/state/autoloop"),
        )
    )
    private_path = private_root / repo_key / run_dir.name / "sync-status.txt"
    status_path = (
        run_dir / "sync-status.txt"
        if (run_dir / "sync-status.txt").exists()
        else private_path
    )
    try:
        lines = [
            line.rstrip()
            for line in status_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            if line.strip()
        ]
    except FileNotFoundError:
        return []
    return lines[:20]


def notification_text(date, state, run_dir, document_url):
    reason = state.get("terminal_reason") or state.get("next_reason") or "unknown"
    status = state.get("terminal_status") or state.get("status") or "failed"
    lines = [
        f"AutoLoop 异常通知 | {date}",
        f"状态：{status}",
        f"原因：{reason}",
        f"已执行 attempt：{len(state.get('attempts', []))}",
    ]
    paths = dirty_paths(run_dir)
    if paths:
        lines.extend(["远端未提交/未跟踪文件：", *[f"- {item}" for item in paths]])
    lines.extend(
        [
            f"实验日志：{document_url}",
            "原始证据正在执行终态归档；若链接缺失，以本通知中的文件清单为准。",
        ]
    )
    return "\n".join(lines)


def notify(date, state_path, run_dir):
    run_dir = Path(run_dir)
    ledger_path = run_dir / "feishu_notification.json"
    existing = read_json(ledger_path, {})
    if existing.get("delivery_verified") is True:
        return 0

    config = read_json(AUTOLOOP_DIR / "feishu.json", {})
    document_url = config.get("url", "")
    cli = find_lark_cli()
    if not cli:
        write_json(
            ledger_path,
            {"status": "failed", "reason": "lark_cli_missing"},
        )
        return 1

    auth_rc, auth, auth_error = run_json([cli, "auth", "status", "--json", "--verify"])
    user = auth.get("identities", {}).get("user", {})
    user_id = user.get("openId", "")
    if auth_rc or not auth.get("verified") or not user_id:
        write_json(
            ledger_path,
            {
                "status": "failed",
                "reason": "user_identity_unavailable",
                "detail": auth_error[:300],
            },
        )
        return 1

    state = read_json(state_path, {})
    text = notification_text(date, state, run_dir, document_url)
    send_rc, sent, send_error = run_json(
        [
            cli,
            "im",
            "+messages-send",
            "--as",
            "bot",
            "--user-id",
            user_id,
            "--text",
            text,
            "--idempotency-key",
            f"autoloop-failure-{date}",
            "--format",
            "json",
        ]
    )
    message_id = nested_value(sent, "message_id")
    if send_rc or sent.get("ok") is not True or not message_id:
        write_json(
            ledger_path,
            {
                "status": "failed",
                "reason": "send_failed",
                "detail": send_error[:300],
            },
        )
        return 1

    read_rc, readback, read_error = run_json(
        [
            cli,
            "im",
            "+messages-mget",
            "--as",
            "bot",
            "--message-ids",
            message_id,
            "--no-reactions",
            "--format",
            "json",
        ]
    )
    verified = (
        read_rc == 0
        and readback.get("ok") is True
        and message_id in json.dumps(readback, ensure_ascii=False)
    )
    write_json(
        ledger_path,
        {
            "status": "delivered" if verified else "failed",
            "delivery_verified": verified,
            "message_id_sha256": hashlib.sha256(message_id.encode()).hexdigest(),
            "recipient_id_sha256": hashlib.sha256(user_id.encode()).hexdigest(),
            "reason": "" if verified else "readback_failed",
            "detail": "" if verified else read_error[:300],
        },
    )
    return 0 if verified else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    parser.add_argument("state_path")
    parser.add_argument("run_dir")
    args = parser.parse_args()
    return notify(args.date, args.state_path, args.run_dir)


if __name__ == "__main__":
    sys.exit(main())
