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
    core_succeeded = state.get("core_outcome") == "success"
    recovered_from = state.get("recovered_from")
    if state.get("user_outcome") == "success" and recovered_from:
        lines = [
            f"AutoLoop 收口已自动修复 | {date}",
            "整体结论：成功",
            "作品与线上验证：成功",
            "飞书实验报告：成功",
            "脱敏证据归档：成功",
            f"已修复问题：{recovered_from}",
            "后续动作：无需人工处理。",
        ]
    elif core_succeeded:
        title = f"AutoLoop 部分成功，收口自动修复中 | {date}"
        report_result = "成功" if state.get("report_rc") == 0 else "失败"
        archive_result = (
            "未执行"
            if "archive_rc" not in state
            else "成功"
            if state.get("archive_rc") == 0
            else "失败"
        )
        lines = [
            title,
            "整体结论：部分成功（作品已上线，可正常使用）",
            "作品与线上验证：成功",
            f"飞书实验报告：{report_result}",
            f"脱敏证据归档：{archive_result}",
            f"收口问题：{reason}",
            "后续动作：AutoLoop 将继续自动修复收口，不会重跑或回退作品。",
        ]
    else:
        lines = [
            f"AutoLoop 任务失败，需要介入 | {date}",
            "整体结论：失败（作品未完成或未通过验证）",
            f"失败原因：{reason}",
        ]
    lines.append(f"已执行 attempt：{len(state.get('attempts', []))}")
    paths = dirty_paths(run_dir)
    if paths:
        lines.extend(["远端未提交/未跟踪文件：", *[f"- {item}" for item in paths]])
    lines.extend(
        [
            f"实验日志：{document_url}",
            "公开证据只包含脱敏内容；归档未完成时以本通知结论为准。",
        ]
    )
    return "\n".join(lines)


def notify(date, state_path, run_dir):
    run_dir = Path(run_dir)
    state = read_json(state_path, {})
    recovered = (
        state.get("user_outcome") == "success"
        and bool(state.get("recovered_from"))
    )
    ledger_path = run_dir / (
        "feishu_recovery_notification.json"
        if recovered
        else "feishu_notification.json"
    )
    existing = read_json(ledger_path, {})
    if existing.get("delivery_verified") is True:
        return 0

    config = read_json(
        Path(
            os.environ.get(
                "AUTOLOOP_FEISHU_CONFIG",
                str(Path.home() / ".config/autoloop/feishu.json"),
            )
        ),
        {},
    )
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
            f"autoloop-terminal-{date}-{state.get('user_outcome', 'failure')}",
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
