#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知识库文档导入脚本 - 通过API方式导入
"""

import os
import re
import sys
import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

BASE_URL = "http://localhost:8080/api/v1"

# 目录到分类的映射
CATEGORY_MAP = {
    "1-quick-start": "操作指南",
    "2-user-guides": "操作指南",
    "3-workflows": "维护规范",
    "4-data-guides": "设备手册",
    "5-troubleshooting": "故障处理",
    "6-case-studies": "最佳实践",
}

TAGS_MAP = {
    "overview.md": "系统概览,快速入门,功能介绍",
    "proposal-workflow.md": "节能方案,操作流程,S1-S5",
    "load-shifting.md": "负荷转移,峰谷电价,调度",
    "energy-saving-flow.md": "节能流程,方案模板,措施",
    "rl-optimization-flow.md": "强化学习,RL优化,自适应",
    "formula-reference.md": "计算公式,PUE,能耗分析",
    "faq.md": "常见问题,FAQ,帮助",
    "error-codes.md": "错误代码,故障排查,解决方案",
    "case-001-cooling-optimization.md": "案例,冷却优化,节能",
    "index.md": "索引,目录,导航",
}


def api_request(method, path, data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"  API Error {e.code}: {error_body[:200]}")
        return None


def login():
    url = f"{BASE_URL}/auth/login"
    data = urllib.parse.urlencode({"username": "admin", "password": "admin123"}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result["access_token"]


def extract_title(content, filename):
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return Path(filename).stem.replace('-', ' ').title()


def get_category(file_path):
    for part in Path(file_path).parts:
        if part in CATEGORY_MAP:
            return CATEGORY_MAP[part]
    return "其他"


def get_tags(filename):
    return TAGS_MAP.get(Path(filename).name, "知识库,文档")


def main():
    docs_dir = Path(__file__).parent.parent.parent / "docs" / "knowledge-base"
    print(f"docs dir: {docs_dir}")

    if not docs_dir.exists():
        print(f"ERROR: {docs_dir} not found")
        return

    # 登录
    print("Logging in...")
    token = login()
    print(f"Got token: {token[:20]}...")

    # 获取现有知识库
    existing = api_request("GET", "/operation/knowledge?limit=100", token=token) or []
    existing_titles = {item["title"] for item in existing}
    print(f"Existing articles: {len(existing_titles)}")

    # 收集并导入
    md_files = list(docs_dir.rglob("*.md"))
    print(f"Found {len(md_files)} markdown files\n")

    imported = 0
    skipped = 0

    for md_file in sorted(md_files):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()

        title = extract_title(content, md_file.name)
        category = get_category(str(md_file))
        tags = get_tags(md_file.name)
        rel = md_file.relative_to(docs_dir)

        print(f"[{rel}]")
        print(f"  title: {title}")
        print(f"  category: {category}")

        if title in existing_titles:
            print(f"  => SKIP (already exists)")
            skipped += 1
            continue

        payload = {
            "title": title,
            "category": category,
            "content": content,
            "tags": tags,
            "is_published": True,
            "author": "system-import"
        }

        result = api_request("POST", "/operation/knowledge", data=payload, token=token)
        if result:
            print(f"  => OK (id={result.get('id')})")
            imported += 1
        else:
            print(f"  => FAILED")

    print(f"\n=== Done ===")
    print(f"Imported: {imported}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()
