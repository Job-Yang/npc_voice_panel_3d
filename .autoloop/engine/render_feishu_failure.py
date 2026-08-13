#!/usr/bin/env python3
import html
import json
import sys
from pathlib import Path


def read_text(path):
    try:
        return path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, UnicodeDecodeError):
        return ""


def trace_failure(trace_path):
    messages = []
    for line in read_text(trace_path).splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            marker = "Failed to refresh token:"
            if marker in line:
                messages.append(line.split(marker, 1)[1].strip())
            continue

        if event.get("type") == "turn.failed":
            message = event.get("error", {}).get("message", "")
        elif event.get("type") == "error":
            message = event.get("message", "")
        else:
            message = ""
        if message:
            messages.append(str(message).strip())
    return next((message for message in reversed(messages) if message), "")


def metrics_failure(metrics_path):
    try:
        metrics = json.loads(read_text(metrics_path))
    except json.JSONDecodeError:
        return ""
    fields = [
        ("agent_rc", metrics.get("agent_rc")),
        ("preflight_rc", metrics.get("preflight_rc")),
        ("input_validation_rc", metrics.get("input_validation_rc")),
        ("creative_validation_rc", metrics.get("creative_validation_rc")),
    ]
    return ", ".join(f"{name}={value}" for name, value in fields if value is not None)


def failure_summary(run_dir):
    supervisor = read_text(run_dir / "supervisor_failure.txt")
    if supervisor:
        return " ".join(supervisor.split())[:600]

    final = read_text(run_dir / "final.txt")
    if final:
        return " ".join(final.split())[:600]

    trace = trace_failure(run_dir / "trae.jsonl")
    if trace:
        return trace[:600]

    error = read_text(run_dir / "ERROR")
    if error:
        return " ".join(error.split())[:600]

    metrics = metrics_failure(run_dir / "metrics.json")
    if metrics:
        return metrics[:600]

    return "任务在形成 Agent 收口前退出，未留下可解析的失败详情。"


def render(run_dir, date, stamp, marker):
    esc = html.escape
    summary = failure_summary(run_dir)
    run_url = (
        "https://github.com/Job-Yang/npc_voice_panel_3d/tree/main/"
        f".autoloop/runs/{stamp}"
    )
    return "\n".join(
        [
            "<hr/>",
            f"<h2>运行异常｜{esc(date)}｜未形成有效实验轮次</h2>",
            (
                "<p><b>状态：</b>定时任务已触发，但 Agent 未生成 "
                "input/journal/作品 commit，因此不计入正式轮次。</p>"
            ),
            f"<p><b>失败摘要：</b>{esc(summary)}</p>",
            f'<p><b>原始证据：</b><a href="{esc(run_url)}">查看本轮 run</a></p>',
            f"<p><code>{esc(marker)}</code></p>",
        ]
    ) + "\n"


def main():
    if len(sys.argv) != 6:
        raise SystemExit(
            "usage: render_feishu_failure.py <run-dir> <date> <stamp> <marker> <output>"
        )
    run_dir, date, stamp, marker, output = sys.argv[1:]
    Path(output).write_text(
        render(Path(run_dir), date, stamp, marker),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
