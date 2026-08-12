#!/usr/bin/env python3
import json
import sys
import xml.etree.ElementTree as ET


def text(node):
    return "".join(node.itertext()).strip()


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


if len(sys.argv) != 5:
    fail("usage: validate_feishu_report.py <fetch-json> <marker> <schema> <success|failure>")

fetch_path, marker, schema, mode = sys.argv[1:]
data = json.load(open(fetch_path, encoding="utf-8"))
content = data["data"]["document"]["content"]
root = ET.fromstring(f"<root>{content}</root>")
children = list(root)

marker_indexes = [index for index, child in enumerate(children) if marker in text(child)]
if len(marker_indexes) != 1:
    fail(f"expected one run marker, got {len(marker_indexes)}")
marker_index = marker_indexes[0]

stage_indexes = [
    index
    for index, child in enumerate(children)
    if child.tag == "h1" and text(child) == "7. 阶段结论"
]
if len(stage_indexes) != 1:
    fail(f"expected one stage conclusion heading, got {len(stage_indexes)}")
stage_index = stage_indexes[0]
if marker_index >= stage_index:
    fail("run marker is not inside section 6 before stage conclusion")

heading_index = next(
    (index for index in range(marker_index - 1, -1, -1) if children[index].tag in {"h1", "h2"}),
    -1,
)
if heading_index < 0 or children[heading_index].tag != "h2":
    fail("round heading is missing or not H2")
heading = text(children[heading_index])

if mode == "failure":
    if not heading.startswith("运行异常｜"):
        fail(f"invalid failure heading: {heading}")
    raise SystemExit(0)

if not heading.startswith("第 ") or " 轮｜" not in heading:
    fail(f"invalid round heading: {heading}")
if schema not in text(children[marker_index]):
    fail(f"report schema marker missing: {schema}")

between = children[heading_index + 1 : marker_index]
tables = [child for child in between if child.tag == "table"]
if len(tables) != 1:
    fail(f"expected exactly one round table, got {len(tables)}")
if any(child.tag in {"h1", "h2", "h3"} for child in between):
    fail("nested headings are forbidden inside a round")

expected_rows = [
    "外部输入",
    "现状与判断",
    "本轮方案",
    "改动",
    "验证与效果",
    "原始证据",
]
actual_rows = []
tbody = tables[0].find("tbody")
if tbody is not None:
    for row in tbody.findall("tr"):
        cells = row.findall("td")
        if cells:
            actual_rows.append(text(cells[0]))
if actual_rows != expected_rows:
    fail(f"round table rows mismatch: {actual_rows}")
