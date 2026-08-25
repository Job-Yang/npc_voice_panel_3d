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

    def test_profile_requires_subtraction_and_personal_site_sync(self):
        profile = (REPO_ROOT / ".autoloop/profile.md").read_text(encoding="utf-8")
        constitution = (REPO_ROOT / ".autoloop/constitution.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("可见对象数量不得净增加", profile)
        self.assertIn("不得再用 `BoxGeometry`", profile)
        self.assertIn("https://jobyang.cn/showcase.json", profile)
        self.assertIn("至少一个必须是**减法或整合方案**", constitution)
        self.assertIn("删除、合并、重排", constitution)

    def test_professional_music_and_profile_feed_are_wired(self):
        source = (REPO_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("assets/music/hearth-and-hammer.mp3", source)
        self.assertIn("assets/music/hearthside-ales.mp3", source)
        self.assertIn("JobYangShowcase:v1", source)
        self.assertNotIn("createOscillator", source)


if __name__ == "__main__":
    unittest.main()
