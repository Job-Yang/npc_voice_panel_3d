#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ENGINE_DIR = Path(__file__).resolve().parent


class ReportFeishuTests(unittest.TestCase):
    def test_render_failure_stops_before_document_append(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            engine = repo / ".autoloop/engine"
            inputs = repo / ".autoloop/inputs"
            journal = repo / ".autoloop/journal"
            run_dir = repo / ".autoloop/runs/test"
            for path in (engine, inputs, journal, run_dir):
                path.mkdir(parents=True, exist_ok=True)

            for name in ("report_feishu.sh", "render_feishu_round.js"):
                shutil.copy2(ENGINE_DIR / name, engine / name)

            date = "2099-01-01"
            (inputs / f"{date}.md").write_text(
                "\n".join(
                    [
                        "# Input",
                        "https://example.com/a",
                        "https://example.com/b",
                        "## 消化与选择",
                        "选择。",
                    ]
                ),
                encoding="utf-8",
            )
            (journal / f"{date}.md").write_text(
                "\n".join(
                    [
                        "## 现状分析",
                        "现状。",
                        "## 创意方案竞争",
                        "方案。",
                        "## 今天的想法",
                        "想法。",
                        "## 为什么这么做",
                        "原因。",
                        "## 做了哪些事",
                        "改动。",
                        "## 最终效果",
                        "效果。",
                    ]
                ),
                encoding="utf-8",
            )
            (repo / ".autoloop/ASK_HUMAN.md").write_text(
                "# ASK_HUMAN\n",
                encoding="utf-8",
            )
            config = Path(directory) / "feishu.json"
            config.write_text(
                json.dumps(
                    {
                        "document_id": "test-document",
                        "report_schema": "AutoLoopReportSchema:v1",
                    }
                ),
                encoding="utf-8",
            )
            lark_log = Path(directory) / "lark.log"
            fake_lark = Path(directory) / "lark-cli"
            fake_lark.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        'printf "%s\\n" "$*" >> "$FAKE_LARK_LOG"',
                        'if [[ "$*" == *"+fetch"* ]]; then',
                        "  printf '%s\\n' '{\"data\":{\"document\":{\"content\":\"\"}}}'",
                        "fi",
                        "exit 0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            fake_lark.chmod(0o755)

            subprocess.run(
                ["git", "init", "-b", "main"],
                cwd=repo,
                check=True,
                capture_output=True,
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
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "base"],
                cwd=repo,
                check=True,
                capture_output=True,
            )

            env = os.environ.copy()
            env.update(
                {
                    "AUTOLOOP_FEISHU_CONFIG": str(config),
                    "AUTOLOOP_LARK_CLI": str(fake_lark),
                    "AUTOLOOP_REPORT_MODE": "success",
                    "FAKE_LARK_LOG": str(lark_log),
                }
            )
            result = subprocess.run(
                [
                    "bash",
                    str(engine / "report_feishu.sh"),
                    str(run_dir),
                    date,
                ],
                cwd=repo,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            report = json.loads(
                (run_dir / "feishu_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["reason"], "report render failed")
            self.assertIn(
                "at least 2 public candidates",
                (run_dir / "feishu_render.log").read_text(encoding="utf-8"),
            )
            self.assertNotIn("+update", lark_log.read_text(encoding="utf-8"))
            self.assertFalse((run_dir / "feishu_update.json").exists())


if __name__ == "__main__":
    unittest.main()
