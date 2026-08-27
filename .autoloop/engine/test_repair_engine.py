#!/usr/bin/env python3
import argparse
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("repair_engine.py")
SPEC = importlib.util.spec_from_file_location("repair_engine", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def git(cwd, *arguments):
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class RepairEngineTests(unittest.TestCase):
    def test_repair_runtime_env_adds_user_tool_directories(self):
        with mock.patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}, clear=True):
            path = MODULE.repair_runtime_env()["PATH"].split(os.pathsep)

        self.assertEqual(path[0], str(Path.home() / ".local/bin"))
        self.assertEqual(path[1], str(Path.home() / ".npm-global/bin"))
        self.assertIn("/usr/bin", path)

    def test_sanitizes_failure_evidence(self):
        sanitized = MODULE.sanitize_evidence(
            "owner@bytedance.com /home/owner/project "
            "access_token=secret https://example.com/private"
        )
        self.assertNotIn("owner@bytedance.com", sanitized)
        self.assertNotIn("/home/owner", sanitized)
        self.assertNotIn("secret", sanitized)
        self.assertNotIn("https://example.com", sanitized)

    def test_rejects_changes_outside_engine(self):
        self.assertTrue(
            MODULE.validate_paths(
                {
                    ".autoloop/engine/supervisor.py",
                    ".autoloop/engine/test_supervisor.py",
                }
            )
        )
        self.assertFalse(MODULE.validate_paths({"index.html"}))
        self.assertFalse(MODULE.validate_paths(set()))
        self.assertFalse(
            MODULE.validate_paths(
                {".autoloop/engine/repair_engine.py"}
            )
        )
        self.assertFalse(
            MODULE.validate_paths(
                {".autoloop/engine/test_only.py"}
            )
        )

    def test_applies_validated_engine_only_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            seed = root / "seed"
            execution = root / "execution"
            private = root / "private"
            fake_agent = root / "fake_agent.py"
            path_record = root / "repair-path.txt"

            git(root, "init", "--bare", str(remote))
            git(root, "init", "-b", "main", str(seed))
            git(seed, "config", "user.name", "Test")
            git(seed, "config", "user.email", "test@example.com")
            engine = seed / ".autoloop/engine"
            engine.mkdir(parents=True)
            (engine / "placeholder.py").write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )
            (engine / "placeholder.sh").write_text(
                "#!/usr/bin/env bash\ntrue\n",
                encoding="utf-8",
            )
            (engine / "render_feishu_round.js").write_text(
                "console.log('ok');\n",
                encoding="utf-8",
            )
            (engine / "verify_web.js").write_text(
                "console.log('ok');\n",
                encoding="utf-8",
            )
            git(seed, "add", ".")
            git(seed, "commit", "-m", "base")
            git(seed, "remote", "add", "origin", str(remote))
            git(seed, "push", "-u", "origin", "main")
            git(root, "clone", "-b", "main", str(remote), str(execution))

            fake_agent.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env python3",
                        "import os",
                        "from pathlib import Path",
                        "repo = Path(os.environ['AUTOLOOP_REPAIR_REPO'])",
                        "Path(os.environ['AUTOLOOP_PATH_RECORD']).write_text(",
                        "    os.environ['PATH'], encoding='utf-8'",
                        ")",
                        "target = repo / '.autoloop/engine/placeholder.py'",
                        "target.write_text('VALUE = 2\\n', encoding='utf-8')",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            fake_agent.chmod(0o755)
            evidence = root / "failure.log"
            evidence.write_text(
                "deterministic failure\n",
                encoding="utf-8",
            )
            result = private / "result.json"
            args = argparse.Namespace(
                date="2099-01-01",
                phase="test",
                evidence=str(evidence),
                execution_repo=str(execution),
                result=str(result),
            )

            with mock.patch.dict(
                os.environ,
                {
                    "AUTOLOOP_REPAIR_COMMAND": str(fake_agent),
                    "AUTOLOOP_PATH_RECORD": str(path_record),
                    "PATH": "/usr/bin:/bin",
                },
                clear=True,
            ):
                rc = MODULE.repair(args)

            self.assertEqual(rc, 0)
            repair_path = path_record.read_text(encoding="utf-8").split(
                os.pathsep
            )
            self.assertEqual(
                repair_path[0],
                str(Path.home() / ".local/bin"),
            )
            self.assertIn(
                "VALUE = 2",
                git(
                    root,
                    "--git-dir",
                    str(remote),
                    "show",
                    "main:.autoloop/engine/placeholder.py",
                ),
            )
            self.assertEqual(
                (
                    execution / ".autoloop/engine/placeholder.py"
                ).read_text(encoding="utf-8"),
                "VALUE = 2\n",
            )


if __name__ == "__main__":
    unittest.main()
