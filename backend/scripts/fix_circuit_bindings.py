r"""
批量修复 PowerDevice 的 circuit_id 绑定

运行方式:
    cd backend
    .venv\Scripts\python.exe scripts/fix_circuit_bindings.py
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
from app.models.device import Device
from app.models.energy import PowerDevice, DistributionCircuit
from sqlalchemy import select
from datetime import datetime

async def fix_circuit_bindings():
    """批量修复 PowerDevice 的 circuit_id 绑定"""

    async with async_session() as session:
        # 1. 构建 circuit_code -> circuit_id 映射
        circuit_result = await session.execute(select(DistributionCircuit))
        circuit_map = {c.circuit_code: c.id for c in circuit_result.scalars().all()}

        print(f"✓ 加载了 {len(circuit_map)} 个配电回路")
        print(f"  回路列表: {', '.join(circuit_map.keys())}")

        # 2. 查找所有未绑定 circuit_id 的 PowerDevice
        result = await session.execute(
            select(PowerDevice, Device)
            .outerjoin(Device, Device.id == PowerDevice.monitor_device_id)
            .where(PowerDevice.circuit_id.is_(None))
        )
        unbound_devices = result.all()

        print(f"\n✓ 找到 {len(unbound_devices)} 个未绑定 circuit_id 的 PowerDevice")

        if not unbound_devices:
            print("✓ 所有设备已正确绑定，无需修复")
            return

        # 3. 按设备类型分组统计
        stats = {}
        for pd, dev in unbound_devices:
            dev_type = dev.device_type if dev else "UNKNOWN"
            stats[dev_type] = stats.get(dev_type, 0) + 1

        print("\n未绑定设备统计:")
        for dev_type, count in sorted(stats.items()):
            print(f"  {dev_type}: {count} 个")

        # 4. 逐个修复
        fixed_count = 0
        failed_count = 0

        print("\n开始修复...")
        for pd, dev in unbound_devices:
            if not dev:
                print(f"  ⚠ {pd.device_code}: 无关联 Device，跳过")
                failed_count += 1
                continue

            circuit_id = infer_circuit_id(dev, circuit_map)

            if circuit_id:
                pd.circuit_id = circuit_id
                pd.updated_at = datetime.now()
                fixed_count += 1
                circuit_code = next((k for k, v in circuit_map.items() if v == circuit_id), "?")
                print(f"  ✓ {pd.device_code} ({dev.device_type}) → {circuit_code}")
            else:
                print(f"  ⚠ {pd.device_code} ({dev.device_type}): 无法推断回路")
                failed_count += 1

        # 5. 提交更改
        await session.commit()

        print("\n修复完成:")
        print(f"  成功: {fixed_count} 个")
        print(f"  失败: {failed_count} 个")
        print(f"  总计: {len(unbound_devices)} 个")


def infer_circuit_id(device: Device, circuit_map: dict) -> int | None:
    """
    根据设备编码和类型智能推断应该绑定的回路ID

    规则:
    - UPS-F1-XX → C-F1-UPS-01
    - UPS-F2-XX → C-F2-UPS-01
    - UPS-F3-XX → C-F3-UPS-01
    - CH-F1-XX (冷机) → C-CH-01
    - CT-F1-XX (冷却塔) → C-CT-01
    - PMP-F1-0[1-4] (冷冻水泵) → C-CHWP-01
    - PMP-F1-0[7-9] (冷却水泵) → C-CWP-01
    - AC-XX (精密空调) → C-AC-01 或 C-AC-02
    - PDU-XX (列头柜) → 根据区域分配
    """
    code = device.device_code
    dev_type = device.device_type

    # UPS 设备
    if dev_type == "UPS":
        if code.startswith("UPS-F1-"):
            return circuit_map.get("C-F1-UPS-01")
        elif code.startswith("UPS-F2-") or code.startswith("F2-UPS-"):
            return circuit_map.get("C-F2-UPS-01")
        elif code.startswith("UPS-F3-") or code.startswith("F3-UPS-"):
            return circuit_map.get("C-F3-UPS-01")

    # 制冷设备
    elif dev_type == "AC":
        if code.startswith("CH-"):
            return circuit_map.get("C-CH-01")
        elif code.startswith("CT-"):
            return circuit_map.get("C-CT-01")
        elif code.startswith("PMP-"):
            # 冷冻水泵 01-04, 冷却水泵 07-09
            if any(code.endswith(f"-0{i}") for i in [1, 2, 3, 4]):
                return circuit_map.get("C-CHWP-01")
            elif any(code.endswith(f"-0{i}") for i in [7, 8, 9]):
                return circuit_map.get("C-CWP-01")
        elif code.startswith("F1-AC-"):
            return circuit_map.get("C-F1-AC-01")
        elif code.startswith("F2-AC-"):
            return circuit_map.get("C-F2-AC-01")
        elif code.startswith("F3-AC-"):
            return circuit_map.get("C-F3-AC-01")
        elif code.startswith("AC-A"):
            return circuit_map.get("C-AC-01")
        elif code.startswith("AC-B"):
            return circuit_map.get("C-AC-02")

    # PDU/IT 设备
    elif dev_type in ("PDU", "IT"):
        area = device.area_code or ""
        if "A1" in area or "A" in code:
            return circuit_map.get("C-A1-01")
        elif "B1" in area or "B" in code:
            return circuit_map.get("C-B1-01")

    # 照明
    elif dev_type == "LIGHT":
        return circuit_map.get("C-LIGHT")

    return None


if __name__ == "__main__":
    print("=" * 60)
    print("PowerDevice circuit_id 批量修复脚本")
    print("=" * 60)
    asyncio.run(fix_circuit_bindings())
    print("=" * 60)
