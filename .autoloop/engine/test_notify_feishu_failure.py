#!/usr/bin/env python3
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("notify_feishu_failure.py")
SPEC = importlib.util.spec_from_file_location("notify_feishu_failure", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NotificationTests(unittest.TestCase):
    def test_partial_success_notification_is_not_self_contradictory(self):
        with tempfile.TemporaryDirectory() as directory:
            text = MODULE.notification_text(
                "2099-01-01",
                {
                    "core_outcome": "success",
                    "user_outcome": "partial_success",
                    "terminal_status": "succeeded",
                    "terminal_reason": "git_archive_failed",
                    "report_rc": 0,
                    "archive_rc": 128,
                    "attempts": [{}],
                },
                Path(directory),
                "https://example.com/doc",
            )

        self.assertIn("部分成功", text)
        self.assertIn("作品与线上验证：成功", text)
        self.assertIn("脱敏证据归档：失败", text)
        self.assertIn("继续自动修复", text)
        self.assertNotIn("状态：succeeded", text)

    def test_core_failure_is_reported_as_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            text = MODULE.notification_text(
                "2099-01-01",
                {
                    "core_outcome": "failure",
                    "terminal_reason": "creative_contract",
                    "attempts": [{}],
                },
                Path(directory),
                "",
            )

        self.assertIn("任务失败，需要介入", text)
        self.assertIn("作品未完成或未通过验证", text)

    def test_recovery_notification_declares_full_success(self):
        with tempfile.TemporaryDirectory() as directory:
            text = MODULE.notification_text(
                "2099-01-01",
                {
                    "core_outcome": "success",
                    "user_outcome": "success",
                    "recovered_from": "git_archive_failed",
                    "report_rc": 0,
                    "archive_rc": 0,
                    "attempts": [{}],
                },
                Path(directory),
                "https://example.com/doc",
            )

        self.assertIn("收口已自动修复", text)
        self.assertIn("整体结论：成功", text)
        self.assertIn("无需人工处理", text)
        self.assertNotIn("部分成功", text)

    def test_notification_includes_captured_dirty_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "sync-status.txt").write_text(
                " M index.html\n?? local-note.txt\n",
                encoding="utf-8",
            )
            text = MODULE.notification_text(
                "2099-01-01",
                {
                    "terminal_status": "failed_exhausted",
                    "terminal_reason": "git_sync_dirty_worktree",
                    "attempts": [{}, {}],
                },
                run_dir,
                "https://example.com/doc",
            )
            self.assertIn("git_sync_dirty_worktree", text)
            self.assertIn("M index.html", text)
            self.assertIn("?? local-note.txt", text)

    def test_send_is_verified_and_sensitive_ids_are_hashed(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            state_path = run_dir / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "terminal_status": "failed_exhausted",
                        "terminal_reason": "test_failure",
                        "attempts": [{}],
                    }
                ),
                encoding="utf-8",
            )
            responses = iter(
                [
                    (
                        0,
                        {
                            "verified": True,
                            "identities": {
                                "user": {
                                    "openId": "ou_private",
                                    "status": "ready",
                                }
                            },
                        },
                        "",
                    ),
                    (
                        0,
                        {
                            "ok": True,
                            "data": {"message": {"message_id": "om_private"}},
                        },
                        "",
                    ),
                    (
                        0,
                        {
                            "ok": True,
                            "data": {"messages": [{"message_id": "om_private"}]},
                        },
                        "",
                    ),
                ]
            )
            with mock.patch.object(
                MODULE, "find_lark_cli", return_value="/fake/lark-cli"
            ), mock.patch.object(MODULE, "run_json", side_effect=responses), mock.patch.object(
                MODULE, "AUTOLOOP_DIR", run_dir
            ):
                (run_dir / "feishu.json").write_text(
                    json.dumps({"url": "https://example.com/doc"}),
                    encoding="utf-8",
                )
                rc = MODULE.notify("2099-01-01", state_path, run_dir)

            self.assertEqual(rc, 0)
            ledger = json.loads(
                (run_dir / "feishu_notification.json").read_text(encoding="utf-8")
            )
            serialized = json.dumps(ledger)
            self.assertTrue(ledger["delivery_verified"])
            self.assertNotIn("ou_private", serialized)
            self.assertNotIn("om_private", serialized)


if __name__ == "__main__":
    unittest.main()
