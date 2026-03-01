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
from app.models.energy import PowerDevice, DistributionCircuit
from app.services.device_sync import DeviceSyncService
from sqlalchemy import select
from datetime import datetime


async def fix_circuit_bindings():
    """批量修复 PowerDevice 的 circuit_id 绑定"""

    async with async_session() as session:
        # 1. 构建 circuit_code -> circuit_id 映射
        circuit_result = await session.execute(select(DistributionCircuit))
        circuit_map = {c.circuit_code: c.id for c in circuit_result.scalars().all()}

        print(f"✓ 加载了 {len(circuit_map)} 个配电回路")
        print(f"  回路列表: {', '.join(sorted(circuit_map.keys()))}")

        # 2. 查找所有未绑定 circuit_id 的 PowerDevice
        result = await session.execute(
            select(PowerDevice)
            .where(PowerDevice.circuit_id.is_(None))
        )
        unbound_devices = result.scalars().all()

        print(f"\n✓ 找到 {len(unbound_devices)} 个未绑定 circuit_id 的 PowerDevice")

        if not unbound_devices:
            print("✓ 所有设备已正确绑定，无需修复")
            return

        # 3. 按设备类型分组统计
        stats = {}
        for pd in unbound_devices:
            dev_type = pd.device_type
            stats[dev_type] = stats.get(dev_type, 0) + 1

        print("\n未绑定设备统计:")
        for dev_type, count in sorted(stats.items()):
            print(f"  {dev_type}: {count} 个")

        # 4. 使用 DeviceSyncService 的推断逻辑逐个修复
        sync_service = DeviceSyncService(session)
        fixed_count = 0
        failed_count = 0
        failed_devices = []

        print("\n开始修复...")
        for pd in unbound_devices:
            # 创建一个临时对象来模拟 Device 接口
            class MockDevice:
                def __init__(self, device_code, device_type, area_code):
                    self.device_code = device_code
                    self.device_type = device_type
                    self.area_code = area_code
            mock_device = MockDevice(pd.device_code, pd.device_type, pd.area_code)
            circuit_id = sync_service._infer_circuit_id(mock_device, circuit_map)
            if circuit_id:
                pd.circuit_id = circuit_id
                pd.updated_at = datetime.now()
                fixed_count += 1
                circuit_code = next((k for k, v in circuit_map.items() if v == circuit_id), "?")
                print(f"  ✓ {pd.device_code} ({pd.device_type}) → {circuit_code}")
            else:
                print(f"  ⚠ {pd.device_code} ({pd.device_type}): 无法推断回路")
                failed_count += 1
                failed_devices.append((pd.device_code, pd.device_type))
        # 5. 提交更改
        await session.commit()

        print("\n修复完成:")
        print(f"  成功: {fixed_count} 个")
        print(f"  失败: {failed_count} 个")
        print(f"  总计: {len(unbound_devices)} 个")

        if failed_devices:
            print("\n失败设备详情:")
            for code, dtype in failed_devices:
                print(f"  - {code} ({dtype})")
            print("\n建议: 请手动为这些设备指定 circuit_id，或在 demo/service.py 中添加对应的配电回路定义")


if __name__ == "__main__":
    print("=" * 60)
    print("PowerDevice Circuit Binding 批量修复工具")
    print("=" * 60)
    asyncio.run(fix_circuit_bindings())
    print("=" * 60)
