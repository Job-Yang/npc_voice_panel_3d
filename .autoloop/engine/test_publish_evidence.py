#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("publish_evidence.py")
SPEC = importlib.util.spec_from_file_location("publish_evidence", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PublishEvidenceTests(unittest.TestCase):
    def test_platform_payload_is_excluded_and_logs_are_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            supervisor = root / "supervisor"
            attempt = root / "attempt"
            output = root / "public"
            (supervisor / "prewarm").mkdir(parents=True)
            attempt.mkdir()
            (supervisor / "state.json").write_text(
                json.dumps(
                    {
                        "schema": "AutoLoopSupervisor:v1",
                        "date": "2099-01-01",
                        "status": "failed_exhausted",
                        "terminal_reason": "static_gate",
                        "recovered_from": "feishu_report_failed",
                        "private_field": "must not publish",
                    }
                ),
                encoding="utf-8",
            )
            (supervisor / "prewarm/version_static.log").write_text(
                "path=/data00/home/private/project\n"
                "user=owner@bytedance.com\n",
                encoding="utf-8",
            )
            (attempt / "feishu_readback.json").write_text(
                '{"url":"https://internal-api-drive-stream.feishu.cn/'
                'download/authcode/?code=secret"}',
                encoding="utf-8",
            )
            (attempt / "metrics.json").write_text(
                '{"agent_rc":78}',
                encoding="utf-8",
            )

            manifest = MODULE.build_pack(
                "2099-01-01",
                supervisor,
                [attempt],
                output,
            )

            self.assertFalse(
                (output / "attempt/feishu_readback.json").exists()
            )
            public_log = (
                output / "prewarm/version_static.log"
            ).read_text(encoding="utf-8")
            self.assertIn("<REMOTE_HOME>", public_log)
            self.assertIn("<REDACTED_INTERNAL_EMAIL>", public_log)
            self.assertNotIn("private_field", (output / "state.json").read_text())
            self.assertIn(
                "feishu_report_failed",
                (output / "state.json").read_text(),
            )
            self.assertFalse(manifest["platform_raw_payloads_published"])
            scan = json.loads(
                (output / "privacy-scan.json").read_text(encoding="utf-8")
            )
            self.assertEqual(scan["status"], "passed")

    def test_scan_rejects_unredacted_platform_url(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "bad.log").write_text(
                "https://bytedance.larkoffice.com/docx/private",
                encoding="utf-8",
            )
            with self.assertRaises(RuntimeError):
                MODULE.scan_pack(output)


if __name__ == "__main__":
    unittest.main()
