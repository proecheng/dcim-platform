#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知识库文档导入脚本

将 docs/knowledge-base/ 目录下的 Markdown 文档导入到系统知识库数据库中。
"""

import sys
import re
import asyncio
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
import logging

logging.disable(logging.WARNING)  # 抑制SQLAlchemy日志避免GBK编码问题

from app.core.database import async_session, engine
from app.models.operation import KnowledgeBase

# 关闭SQLAlchemy echo
engine.echo = False


# 目录到分类的映射
CATEGORY_MAP = {
    "1-quick-start": "操作指南",
    "2-user-guides": "操作指南",
    "3-workflows": "维护规范",
    "4-data-guides": "设备手册",
    "5-troubleshooting": "故障处理",
    "6-case-studies": "最佳实践",
}

# 文件到标签的映射
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


def extract_title(content: str, filename: str) -> str:
    """从 Markdown 内容中提取标题"""
    # 尝试匹配一级标题
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # 如果没有找到，使用文件名
    name = Path(filename).stem
    return name.replace("-", " ").replace("_", " ").title()


def get_category_from_path(file_path: str) -> str:
    """根据文件路径获取分类"""
    parts = Path(file_path).parts
    for part in parts:
        if part in CATEGORY_MAP:
            return CATEGORY_MAP[part]
    return "其他"


def get_tags(filename: str) -> str:
    """获取文件对应的标签"""
    basename = Path(filename).name
    return TAGS_MAP.get(basename, "知识库,文档")


async def import_documents(docs_dir: str, dry_run: bool = False):
    """导入知识库文档"""

    docs_path = Path(docs_dir)
    if not docs_path.exists():
        print(f"错误: 目录不存在 {docs_dir}")
        return

    # 收集所有 Markdown 文件
    md_files = list(docs_path.rglob("*.md"))
    print(f"找到 {len(md_files)} 个 Markdown 文件")

    if dry_run:
        print("\n=== 预览模式 (不会实际写入数据库) ===\n")

    imported = 0
    skipped = 0

    async with async_session() as db:
        for md_file in md_files:
            try:
                # 读取文件内容
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # 提取信息
                title = extract_title(content, md_file.name)
                category = get_category_from_path(str(md_file))
                tags = get_tags(md_file.name)
                relative_path = md_file.relative_to(docs_path)

                print(f"\n处理: {relative_path}")
                print(f"  标题: {title}")
                print(f"  分类: {category}")
                print(f"  标签: {tags}")

                if dry_run:
                    imported += 1
                    continue

                # 检查是否已存在
                stmt = select(KnowledgeBase).where(KnowledgeBase.title == title)
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    print(f"  状态: 已存在 (ID: {existing.id})，更新内容")
                    existing.content = content
                    existing.category = category
                    existing.tags = tags
                    existing.updated_at = datetime.now()
                    skipped += 1
                else:
                    # 创建新记录
                    knowledge = KnowledgeBase(
                        title=title,
                        category=category,
                        content=content,
                        tags=tags,
                        author="系统导入",
                        is_published=True,
                        view_count=0,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )
                    db.add(knowledge)
                    print("  状态: 新建")
                    imported += 1

            except Exception as e:
                print(f"  错误: {e}")
                continue

        if not dry_run:
            await db.commit()

    print("\n=== 导入完成 ===")
    print(f"新增: {imported} 条")
    print(f"更新: {skipped} 条")


async def list_knowledge():
    """列出现有知识库条目"""
    async with async_session() as db:
        stmt = select(KnowledgeBase).order_by(KnowledgeBase.category, KnowledgeBase.title)
        result = await db.execute(stmt)
        items = result.scalars().all()

        print(f"\n=== 现有知识库条目 ({len(items)} 条) ===\n")

        current_category = None
        for item in items:
            if item.category != current_category:
                current_category = item.category
                print(f"\n【{current_category or '未分类'}】")

            status = "✓" if item.is_published else "○"
            print(f"  {status} [{item.id:3d}] {item.title} (阅读:{item.view_count})")


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="知识库文档导入工具")
    parser.add_argument("--dry-run", "-n", action="store_true", help="预览模式，不实际写入数据库")
    parser.add_argument("--list", "-l", action="store_true", help="列出现有知识库条目")
    parser.add_argument(
        "--dir", "-d", type=str, default=str(project_root.parent / "docs" / "knowledge-base"), help="知识库文档目录"
    )

    args = parser.parse_args()

    if args.list:
        await list_knowledge()
    else:
        print(f"知识库目录: {args.dir}")
        await import_documents(args.dir, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
