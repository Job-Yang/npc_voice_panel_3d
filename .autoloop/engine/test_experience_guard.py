#!/usr/bin/env python3
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class ExperienceGuardTests(unittest.TestCase):
    def test_rules_only_delegate_final_3d_model_creation(self):
        profile = (REPO_ROOT / ".autoloop/profile.md").read_text(encoding="utf-8")
        constitution = (REPO_ROOT / ".autoloop/constitution.md").read_text(
            encoding="utf-8"
        )
        ask_human = (REPO_ROOT / ".autoloop/ASK_HUMAN.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("不限制", (REPO_ROOT / ".autoloop/HUMAN_FEEDBACK.md").read_text(
            encoding="utf-8"
        ))
        self.assertIn("不要自行手工绘制或用代码拼装最终 3D 模型", profile)
        self.assertIn("可以先占位并完成模型", profile)
        self.assertIn("https://jobyang.cn/showcase.js", profile)
        self.assertIn("## 3D 模型协作约定", constitution)
        self.assertIn("不因是否需要 3D 模型限制选择", constitution)
        self.assertIn("## 3D 资产需求模板", ask_human)
        self.assertIn("模型描述", ask_human)
        self.assertIn("建议文件名", ask_human)

    def test_professional_music_and_profile_feed_are_wired(self):
        source = (REPO_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("assets/music/hearth-and-hammer.mp3", source)
        self.assertIn("assets/music/hearthside-ales.mp3", source)
        self.assertIn("JobYangShowcase:v1", source)
        self.assertNotIn("createOscillator", source)


if __name__ == "__main__":
    unittest.main()
