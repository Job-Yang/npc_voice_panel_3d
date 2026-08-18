#!/usr/bin/env python3
"""Return the block IDs for the report section containing one AutoLoop marker."""

import json
import sys
import xml.etree.ElementTree as ET


def node_text(node):
    return "".join(node.itertext()).strip()


def main():
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: find_feishu_report_blocks.py <fetch-json> <marker>"
        )
    fetch_path, marker = sys.argv[1:]
    data = json.load(open(fetch_path, encoding="utf-8"))
    content = data["data"]["document"]["content"]
    root = ET.fromstring(f"<root>{content}</root>")
    children = list(root)

    marker_indexes = [
        index
        for index, child in enumerate(children)
        if marker in node_text(child)
    ]
    if len(marker_indexes) != 1:
        raise SystemExit(f"expected one marker, got {len(marker_indexes)}")
    marker_index = marker_indexes[0]
    heading_index = next(
        (
            index
            for index in range(marker_index - 1, -1, -1)
            if children[index].tag in {"h1", "h2"}
        ),
        -1,
    )
    if heading_index < 0 or children[heading_index].tag != "h2":
        raise SystemExit("report heading not found")

    ids = [
        child.attrib["id"]
        for child in children[heading_index : marker_index + 1]
        if child.attrib.get("id")
    ]
    if not ids:
        raise SystemExit("report block IDs not found")
    print(",".join(ids))


if __name__ == "__main__":
    main()
