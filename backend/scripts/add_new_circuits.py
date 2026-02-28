r"""
添加新的配电回路定义到数据库

运行方式:
    cd backend
    .venv\Scripts\python.exe scripts/add_new_circuits.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 设置控制台编码为 UTF-8
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

from app.core.database import async_session
from app.models.energy import DistributionCircuit, DistributionPanel
from sqlalchemy import select


# 新增的配电回路定义
NEW_CIRCUITS = [
    # F2楼层PDU回路
    {
        "circuit_code": "C-F2-PDU-01",
        "circuit_name": "F2 PDU回路1",
        "panel_code": "F2-PANEL-001",
        "load_type": "IT",
        "rated_current": 200,
        "is_shiftable": False,
    },
    {
        "circuit_code": "C-F2-PDU-02",
        "circuit_name": "F2 PDU回路2",
        "panel_code": "F2-PANEL-002",
        "load_type": "IT",
        "rated_current": 200,
        "is_shiftable": False,
    },
    # F2楼层冷通道回路
    {
        "circuit_code": "C-F2-CA-01",
        "circuit_name": "F2 冷通道回路",
        "panel_code": "F2-PANEL-003",
        "load_type": "AC",
        "rated_current": 150,
        "is_shiftable": True,
        "shift_priority": 11,
    },
    # F3楼层PDU回路
    {
        "circuit_code": "C-F3-PDU-01",
        "circuit_name": "F3 PDU回路1",
        "panel_code": "F3-PANEL-001",
        "load_type": "IT",
        "rated_current": 200,
        "is_shiftable": False,
    },
    {
        "circuit_code": "C-F3-PDU-02",
        "circuit_name": "F3 PDU回路2",
        "panel_code": "F3-PANEL-002",
        "load_type": "IT",
        "rated_current": 200,
        "is_shiftable": False,
    },
    # F3楼层冷通道回路
    {
        "circuit_code": "C-F3-CA-01",
        "circuit_name": "F3 冷通道回路",
        "panel_code": "F3-PANEL-003",
        "load_type": "AC",
        "rated_current": 150,
        "is_shiftable": True,
        "shift_priority": 12,
    },
    # F4楼层PDU回路
    {
        "circuit_code": "C-F4-PDU-01",
        "circuit_name": "F4 PDU回路1",
        "panel_code": "F4-PANEL-001",
        "load_type": "IT",
        "rated_current": 200,
        "is_shiftable": False,
    },
    {
        "circuit_code": "C-F4-PDU-02",
        "circuit_name": "F4 PDU回路2",
        "panel_code": "F4-PANEL-002",
        "load_type": "IT",
        "rated_current": 200,
        "is_shiftable": False,
    },
    # F4楼层冷通道回路
    {
        "circuit_code": "C-F4-CA-01",
        "circuit_name": "F4 冷通道回路",
        "panel_code": "F4-PANEL-003",
        "load_type": "AC",
        "rated_current": 150,
        "is_shiftable": True,
        "shift_priority": 13,
    },
    # 水泵回路（扩展）
    {
        "circuit_code": "C-PMP-01",
        "circuit_name": "水泵回路1",
        "panel_code": "COOLING-PANEL-002",
        "load_type": "AC",
        "rated_current": 80,
        "is_shiftable": True,
        "shift_priority": 14,
    },
    {
        "circuit_code": "C-PMP-02",
        "circuit_name": "水泵回路2",
        "panel_code": "COOLING-PANEL-002",
        "load_type": "AC",
        "rated_current": 80,
        "is_shiftable": True,
        "shift_priority": 15,
    },
    # 室外机回路
    {
        "circuit_code": "C-AC-OUT-01",
        "circuit_name": "室外机回路",
        "panel_code": "AC-PANEL-002",
        "load_type": "AC",
        "rated_current": 100,
        "is_shiftable": True,
        "shift_priority": 16,
    },
    # A区冷通道回路
    {
        "circuit_code": "C-CA-A-01",
        "circuit_name": "A区冷通道回路",
        "panel_code": "AC-PANEL-003",
        "load_type": "AC",
        "rated_current": 100,
        "is_shiftable": True,
        "shift_priority": 17,
    },
]


async def add_new_circuits():
    """添加新的配电回路到数据库"""

    async with async_session() as session:
        # 1. 检查现有回路
        result = await session.execute(select(DistributionCircuit))
        existing_circuits = {c.circuit_code: c for c in result.scalars().all()}

        print(f"✓ 现有配电回路: {len(existing_circuits)} 个")

        # 2. 获取所有配电柜（用于关联）
        panel_result = await session.execute(select(DistributionPanel))
        panels = {p.panel_code: p for p in panel_result.scalars().all()}

        print(f"✓ 现有配电柜: {len(panels)} 个")

        # 3. 添加新回路
        added_count = 0
        skipped_count = 0

        print("\n开始添加新回路...")
        for circuit_data in NEW_CIRCUITS:
            circuit_code = circuit_data["circuit_code"]

            if circuit_code in existing_circuits:
                print(f"  ⊙ {circuit_code}: 已存在，跳过")
                skipped_count += 1
                continue

            # 查找对应的配电柜
            panel_code = circuit_data.pop("panel_code")
            panel = panels.get(panel_code)

            if not panel:
                print(f"  ⚠ {circuit_code}: 配电柜 {panel_code} 不存在，跳过")
                skipped_count += 1
                continue

            # 创建新回路
            new_circuit = DistributionCircuit(
                **circuit_data,
                panel_id=panel.id
            )
            session.add(new_circuit)
            added_count += 1
            print(f"  ✓ {circuit_code}: {circuit_data['circuit_name']}")

        # 4. 提交更改
        await session.commit()

        print("\n添加完成:")
        print(f"  新增: {added_count} 个")
        print(f"  跳过: {skipped_count} 个")
        print(f"  总计: {len(NEW_CIRCUITS)} 个")


if __name__ == "__main__":
    print("=" * 60)
    print("配电回路扩展工具")
    print("=" * 60)
    asyncio.run(add_new_circuits())
    print("=" * 60)
