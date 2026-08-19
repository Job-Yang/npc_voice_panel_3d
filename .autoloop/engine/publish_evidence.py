#!/usr/bin/env python3
"""Build a deterministic, redacted public evidence pack from private run artifacts."""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


PLATFORM_RAW_NAMES = {
    "feishu_append.md",
    "feishu_append.xml",
    "feishu_marker_check.json",
    "feishu_media.json",
    "feishu_move_stage.json",
    "feishu_readback.json",
    "feishu_structure.json",
    "feishu_update.json",
}
PUBLIC_TEXT_NAMES = {
    "ERROR",
    "SKIPPED",
    "final.txt",
    "supervisor_attempt.log",
    "supervisor_failure.txt",
    "supervisor_notification.log",
    "supervisor_report.log",
    "version_static.log",
}
PUBLIC_JSON_NAMES = {
    "creative_validation.json",
    "input_validation.json",
    "metrics.json",
    "preflight.json",
    "sync_failure.json",
    "version_gate.json",
}
REDACTIONS = (
    (
        re.compile(
            r"https?://internal-api-drive-stream\.feishu\.cn/\S+",
            re.IGNORECASE,
        ),
        "<REDACTED_FEISHU_MEDIA_URL>",
    ),
    (
        re.compile(
            r"https?://[^\s\"'<>]*(?:larkoffice|feishu)\.(?:com|cn)/\S*",
            re.IGNORECASE,
        ),
        "<REDACTED_INTERNAL_DOC_URL>",
    ),
    (
        re.compile(r"\b(?:ou|om|oc|cli)_[0-9a-z]+\b", re.IGNORECASE),
        "<REDACTED_PLATFORM_ID>",
    ),
    (
        re.compile(r"\b(?:doxcn|docx/)[0-9A-Za-z_-]{12,}\b"),
        "<REDACTED_DOCUMENT_ID>",
    ),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@bytedance\.com\b", re.IGNORECASE),
        "<REDACTED_INTERNAL_EMAIL>",
    ),
    (
        re.compile(r"(?:/data00)?/home/[^/\s\"']+"),
        "<REMOTE_HOME>",
    ),
    (
        re.compile(r"/Users/[^/\s\"']+"),
        "<LOCAL_HOME>",
    ),
    (
        re.compile(
            r"(?i)(access_token|refresh_token|app_secret|authorization)"
            r"([\"'\s:=]+)([^\"'\s,}]+)"
        ),
        r"\1\2<REDACTED_SECRET>",
    ),
)
FORBIDDEN = (
    re.compile(r"authcode", re.IGNORECASE),
    re.compile(r"internal-api-drive-stream", re.IGNORECASE),
    re.compile(r"https?://[^\s\"']*(?:larkoffice|feishu)\.", re.IGNORECASE),
    re.compile(r"\b(?:ou|om|oc|cli)_[0-9a-z]+\b", re.IGNORECASE),
    re.compile(r"(?:/data00)?/home/[^<\s\"']+"),
    re.compile(r"/Users/[^<\s\"']+"),
    re.compile(
        r"(?i)(?:access_token|refresh_token|app_secret|authorization)"
        r"[\"'\s:=]+(?!<REDACTED_SECRET>)"
    ),
)


def redact(text):
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def selected_state(path):
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    keep = {
        "schema",
        "date",
        "status",
        "attempts",
        "finalize_attempts",
        "prewarm",
        "prewarm_failures",
        "core_outcome",
        "user_outcome",
        "terminal_status",
        "terminal_reason",
        "report_rc",
        "notification_rc",
        "archive_rc",
    }
    return {key: state[key] for key in keep if key in state}


def copy_public_file(source, destination):
    text = source.read_text(encoding="utf-8", errors="replace")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(redact(text), encoding="utf-8")


def build_pack(date, supervisor_root, attempt_dirs, output):
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    excluded = []

    state = selected_state(Path(supervisor_root) / "state.json")
    (output / "state.json").write_text(
        redact(json.dumps(state, ensure_ascii=False, indent=2)) + "\n",
        encoding="utf-8",
    )

    roots = [Path(supervisor_root) / "prewarm", *map(Path, attempt_dirs)]
    for root in roots:
        if not root.exists():
            continue
        prefix = "prewarm" if root.name == "prewarm" else root.name
        for source in sorted(path for path in root.rglob("*") if path.is_file()):
            if source.name in PLATFORM_RAW_NAMES:
                excluded.append(str(source))
                continue
            if source.name == "feishu_notification.json":
                copy_public_file(source, output / prefix / source.name)
                continue
            if source.name in PUBLIC_TEXT_NAMES or source.name in PUBLIC_JSON_NAMES:
                copy_public_file(source, output / prefix / source.name)
            else:
                excluded.append(str(source))

    manifest = {
        "schema": "AutoLoopPublicEvidence:v1",
        "date": date,
        "policy": "allowlist_and_redact",
        "platform_raw_payloads_published": False,
        "excluded_file_count": len(excluded),
        "published_files": sorted(
            str(path.relative_to(output))
            for path in output.rglob("*")
            if path.is_file()
        ),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    scan_pack(output)
    return manifest


def scan_pack(output):
    findings = []
    for path in sorted(Path(output).rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FORBIDDEN:
            if pattern.search(text):
                findings.append(
                    {
                        "file": str(path),
                        "pattern": pattern.pattern,
                    }
                )
    report = {
        "status": "passed" if not findings else "failed",
        "finding_count": len(findings),
        "findings": findings,
    }
    (Path(output) / "privacy-scan.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if findings:
        raise RuntimeError("public evidence privacy scan failed")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--supervisor-root", required=True)
    parser.add_argument("--attempt-dir", action="append", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        build_pack(
            args.date,
            Path(args.supervisor_root),
            [Path(item) for item in args.attempt_dir],
            Path(args.output),
        )
        return 0
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
