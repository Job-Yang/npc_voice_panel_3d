#!/usr/bin/env python3
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class ExperienceGuardTests(unittest.TestCase):
    def test_runtime_does_not_build_visible_props_from_primitives(self):
        source = (REPO_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertNotIn("function makeProp", source)
        self.assertNotIn("const loopBoard =", source)
        self.assertNotIn("const processForge =", source)
        self.assertNotIn("const intakeTray =", source)
        self.assertIn("createHotspot('forge'", source)

    def test_profile_requires_asset_handoff_and_personal_site_sync(self):
        profile = (REPO_ROOT / ".autoloop/profile.md").read_text(encoding="utf-8")
        constitution = (REPO_ROOT / ".autoloop/constitution.md").read_text(
            encoding="utf-8"
        )
        ask_human = (REPO_ROOT / ".autoloop/ASK_HUMAN.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("不得把 `BoxGeometry`", profile)
        self.assertIn("完整 3D 资产需求单", profile)
        self.assertIn("?debugAssets=1", profile)
        self.assertIn("https://jobyang.cn/showcase.js", profile)
        self.assertIn("至少一个必须是**减法或整合方案**", constitution)
        self.assertIn("## 3D 资产半协作协议", constitution)
        self.assertIn("asset_pending", constitution)
        self.assertIn("## 3D 资产需求模板", ask_human)
        self.assertIn("约定文件名", ask_human)

    def test_professional_music_and_profile_feed_are_wired(self):
        source = (REPO_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("assets/music/hearth-and-hammer.mp3", source)
        self.assertIn("assets/music/hearthside-ales.mp3", source)
        self.assertIn("JobYangShowcase:v1", source)
        self.assertNotIn("createOscillator", source)


if __name__ == "__main__":
    unittest.main()
