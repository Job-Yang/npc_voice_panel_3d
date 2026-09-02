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
        self.assertIn("## 3D 模型协作约定", constitution)
        self.assertIn("不因是否需要 3D 模型限制选择", constitution)
        self.assertIn("## 3D 资产需求模板", ask_human)
        self.assertIn("模型描述", ask_human)
        self.assertIn("建议文件名", ask_human)

    def test_page_is_independent_from_profile_site(self):
        source = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
        profile = (REPO_ROOT / ".autoloop/profile.md").read_text(encoding="utf-8")
        experiment = (REPO_ROOT / ".autoloop/EXPERIMENT.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("独立 3D 互动页面", profile)
        self.assertIn("独立铁匠铺 3D 页面", experiment)
        forbidden_runtime_dependencies = (
            "JobYangShowcase:v1",
            "showcase.js",
            "jobyang.cn",
            "PROFILE_SITE_URL",
            "PROFILE_FEED_URL",
            "loadProfileFeed",
            "applyProfileFeed",
            "主页欢迎页",
            "这里是主页",
        )
        for dependency in forbidden_runtime_dependencies:
            with self.subTest(dependency=dependency):
                self.assertNotIn(dependency, source)
                self.assertNotIn(dependency, profile)

    def test_professional_music_is_wired_without_generated_audio(self):
        source = (REPO_ROOT / "index.html").read_text(encoding="utf-8")

        self.assertIn("assets/music/hearth-and-hammer.mp3", source)
        self.assertIn("assets/music/hearthside-ales.mp3", source)
        self.assertNotIn("createOscillator", source)


if __name__ == "__main__":
    unittest.main()
