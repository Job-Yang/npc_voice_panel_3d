#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path


def section(markdown, title):
    match = re.search(
        rf"^## {re.escape(title)}\s*$([\s\S]*?)(?=^## |\Z)",
        markdown,
        re.MULTILINE,
    )
    return match.group(1).strip() if match else ""


def fail(result_path, errors):
    result_path.write_text(
        json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(2)


if len(sys.argv) != 4:
    raise SystemExit(
        "usage: validate_creative_round.py <input-card> <journal> <result-json>"
    )

input_path, journal_path, result_path = map(Path, sys.argv[1:])
errors = []
if not input_path.is_file():
    errors.append(f"missing input card: {input_path}")
if not journal_path.is_file():
    errors.append(f"missing journal: {journal_path}")
if errors:
    fail(result_path, errors)

input_card = input_path.read_text(encoding="utf-8")
journal = journal_path.read_text(encoding="utf-8")
competition = section(input_card, "创意方案竞争")
if not competition:
    errors.append("input card missing exact section: ## 创意方案竞争")

proposal_matches = list(
    re.finditer(r"^### 方案 ([ABC])(?:[：:].*)?$", competition, re.MULTILINE)
)
proposal_names = [match.group(1) for match in proposal_matches]
if proposal_names != ["A", "B", "C"]:
    errors.append(f"expected proposal headings A/B/C, got {proposal_names}")

dimensions = ["新颖度", "访客价值", "场景贴合度", "视觉影响", "实现风险"]
for index, match in enumerate(proposal_matches):
    end = (
        proposal_matches[index + 1].start()
        if index + 1 < len(proposal_matches)
        else len(competition)
    )
    body = competition[match.end() : end]
    for dimension in dimensions:
        if not re.search(rf"{dimension}\s*[：:|]\s*[1-5](?:\s*/\s*5)?", body):
            errors.append(f"方案 {match.group(1)} missing score: {dimension}")

selection = section(input_card, "选择与完整体验")
if not selection:
    errors.append("input card missing exact section: ## 选择与完整体验")
else:
    for phrase in ["最终选择", "访客会看到什么", "访客能做什么", "访客得到什么"]:
        if phrase not in selection:
            errors.append(f"selection section missing: {phrase}")

journal_competition = section(journal, "创意方案竞争")
if not journal_competition:
    errors.append("journal missing exact section: ## 创意方案竞争")

visual = section(journal, "可感知变化验证")
if not visual:
    errors.append("journal missing exact section: ## 可感知变化验证")
else:
    for phrase in ["5 秒", "完整体验", "遮挡", "构图"]:
        if phrase not in visual:
            errors.append(f"visual validation missing conclusion: {phrase}")
    screenshot_paths = sorted(
        set(re.findall(r"\.autoloop/journal/assets/[^\s`)]+\.png", visual))
    )
    if len(screenshot_paths) < 2:
        errors.append("visual validation must reference previous and current screenshots")

if errors:
    fail(result_path, errors)

result_path.write_text(
    json.dumps(
        {
            "status": "passed",
            "proposal_count": 3,
            "score_dimensions": dimensions,
            "visual_comparison_declared": True,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
