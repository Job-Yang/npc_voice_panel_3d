#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("render_feishu_round.js")
REPO_ROOT = SCRIPT.parent.parent.parent


def journal():
    return "\n".join(
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
    )


def render(input_text, ask_human_text=""):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        input_path = root / "input.md"
        journal_path = root / "journal.md"
        output_path = root / "report.xml"
        meta_path = root / "meta.json"
        ask_human_path = root / "ASK_HUMAN.md"
        input_path.write_text(input_text, encoding="utf-8")
        journal_path.write_text(journal(), encoding="utf-8")
        ask_human_path.write_text(ask_human_text, encoding="utf-8")
        meta_path.write_text(
            json.dumps(
                {
                    "round": 1,
                    "date": "2099-01-01",
                    "subject": "test",
                    "commit": "abc123",
                    "commit_url": "https://example.com/commit",
                    "input_url": "https://example.com/input",
                    "journal_url": "https://example.com/journal",
                    "ask_human_url": "https://example.com/ask-human",
                    "run_url": "https://example.com/run",
                    "marker": "AutoLoopRun:2099-01-01",
                }
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                "node",
                str(SCRIPT),
                str(input_path),
                str(journal_path),
                str(output_path),
                str(meta_path),
                str(ask_human_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        return result, (
            output_path.read_text(encoding="utf-8")
            if output_path.exists()
            else ""
        )


class RenderFeishuRoundTests(unittest.TestCase):
    def test_renders_numbered_public_sources(self):
        real_input = (
            REPO_ROOT / ".autoloop/inputs/2026-08-21.md"
        ).read_text(encoding="utf-8")
        result, output = render(real_input)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Sketching the Impossible", output)
        self.assertIn("Making an entrance", output)
        self.assertIn("J.B. Schlegelmilch", output)
        self.assertIn("A Paper Tear", output)

    def test_keeps_legacy_candidate_format(self):
        result, output = render(
            "\n".join(
                [
                    "## 候选 1：来源甲",
                    "URL: https://example.com/a",
                    "## 候选 2：来源乙",
                    "URL: https://example.com/b",
                    "## 消化与选择",
                    "选择。",
                ]
            )
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("来源甲", output)
        self.assertIn("来源乙", output)

    def test_renders_current_asset_request_for_human(self):
        result, output = render(
            "\n".join(
                [
                    "## 候选 1：来源甲",
                    "URL: https://example.com/a",
                    "## 候选 2：来源乙",
                    "URL: https://example.com/b",
                    "## 消化与选择",
                    "选择。",
                ]
            ),
            "\n".join(
                [
                    "# ASK_HUMAN",
                    "## 2099-01-01 · 3D 资产需求：铁匠铺信箱",
                    "- 状态：`asset_requested`",
                    "- 约定文件名：`assets/smithy_mailbox.glb`",
                ]
            ),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("需要主人协作", output)
        self.assertIn("铁匠铺信箱", output)
        self.assertIn("assets/smithy_mailbox.glb", output)
        self.assertIn("https://example.com/ask-human", output)


if __name__ == "__main__":
    unittest.main()
