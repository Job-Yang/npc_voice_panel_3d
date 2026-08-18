#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("find_feishu_report_blocks.py")


class FindReportBlocksTests(unittest.TestCase):
    def test_returns_only_target_report_blocks(self):
        content = (
            '<h2 id="h-old">运行异常｜2099-01-01｜未形成有效实验轮次</h2>'
            '<p id="p-old">状态</p>'
            '<p id="m-old">AutoLoopRun:2099-01-01</p>'
            '<h1 id="stage">7. 阶段结论</h1>'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fetch.json"
            path.write_text(
                json.dumps({"data": {"document": {"content": content}}}),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    str(path),
                    "AutoLoopRun:2099-01-01",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.stdout.strip(), "h-old,p-old,m-old")
        self.assertNotIn("stage", result.stdout)


if __name__ == "__main__":
    unittest.main()
