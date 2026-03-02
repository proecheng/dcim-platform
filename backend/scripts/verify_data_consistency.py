r"""
验证所有页面的数据一致性

检查项：
1. UPS 监控页（/power/ups）- 查询 UPSDevice + Device
2. 配电拓扑页（/power/topology）- 查询 PowerDevice + DistributionCircuit
3. 设备管理页（/device/list）- 查询 Device

运行方式:
    cd backend
    .venv\Scripts\python.exe scripts/verify_data_consistency.py
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
from app.models.power import UPSDevice
from app.models.energy import PowerDevice, DistributionCircuit
from sqlalchemy import select, func


async def verify_consistency():
    """验证数据一致性"""

    async with async_session() as session:
        print("=" * 80)
        print("数据一致性验证")
        print("=" * 80)

        # 1. UPS 设备一致性检查
        print("\n【1】UPS 设备一致性检查")
        print("-" * 80)

        # Device 表中的 UPS
        device_ups_count = (await session.execute(
            select(func.count(Device.id)).where(Device.device_type == "UPS", Device.is_enabled == True)
        )).scalar()

        # UPSDevice 扩展表
        ups_device_count = (await session.execute(
            select(func.count(UPSDevice.id))
        )).scalar()

        # PowerDevice 表中的 UPS
        power_ups_count = (await session.execute(
            select(func.count(PowerDevice.id)).where(PowerDevice.device_type == "UPS", PowerDevice.is_enabled == True)
        )).scalar()

        # PowerDevice 中有 circuit_id 的 UPS
        power_ups_with_circuit = (await session.execute(
            select(func.count(PowerDevice.id)).where(
                PowerDevice.device_type == "UPS",
                PowerDevice.is_enabled == True,
                PowerDevice.circuit_id.isnot(None)
            )
        )).scalar()

        print(f"Device 表 UPS 数量: {device_ups_count}")
        print(f"UPSDevice 扩展表数量: {ups_device_count}")
        print(f"PowerDevice 表 UPS 数量: {power_ups_count}")
        print(f"  - 已绑定 circuit_id: {power_ups_with_circuit}")
        print(f"  - 未绑定 circuit_id: {power_ups_count - power_ups_with_circuit}")

        if device_ups_count == ups_device_count == power_ups_count:
            print("✓ UPS 设备数量一致")
        else:
            print("✗ UPS 设备数量不一致！")

        if power_ups_with_circuit == power_ups_count:
            print("✓ 所有 UPS 已绑定 circuit_id")
        else:
            print(f"✗ 有 {power_ups_count - power_ups_with_circuit} 个 UPS 未绑定 circuit_id")

        # 2. 配电拓扑一致性检查
        print("\n【2】配电拓扑一致性检查")
        print("-" * 80)

        # 所有 PowerDevice
        total_power_devices = (await session.execute(
            select(func.count(PowerDevice.id)).where(PowerDevice.is_enabled == True)
        )).scalar()

        # 已绑定 circuit_id 的 PowerDevice
        power_with_circuit = (await session.execute(
            select(func.count(PowerDevice.id)).where(
                PowerDevice.is_enabled == True,
                PowerDevice.circuit_id.isnot(None)
            )
        )).scalar()

        # 配电回路数量
        circuit_count = (await session.execute(
            select(func.count(DistributionCircuit.id)).where(DistributionCircuit.is_enabled == True)
        )).scalar()

        print(f"PowerDevice 总数: {total_power_devices}")
        print(f"  - 已绑定 circuit_id: {power_with_circuit} ({power_with_circuit/total_power_devices*100:.1f}%)")
        print(f"  - 未绑定 circuit_id: {total_power_devices - power_with_circuit}")
        print(f"配电回路总数: {circuit_count}")

        if power_with_circuit == total_power_devices:
            print("✓ 所有设备已绑定配电回路")
        else:
            print(f"✗ 有 {total_power_devices - power_with_circuit} 个设备未绑定配电回路")

        # 3. 设备类型分布
        print("\n【3】设备类型分布")
        print("-" * 80)

        # Device 表设备类型统计
        device_types = (await session.execute(
            select(Device.device_type, func.count(Device.id))
            .where(Device.is_enabled == True)
            .group_by(Device.device_type)
        )).all()

        print("Device 表设备类型:")
        for dev_type, count in sorted(device_types, key=lambda x: x[1], reverse=True):
            print(f"  {dev_type}: {count}")

        # PowerDevice 表设备类型统计
        power_types = (await session.execute(
            select(PowerDevice.device_type, func.count(PowerDevice.id))
            .where(PowerDevice.is_enabled == True)
            .group_by(PowerDevice.device_type)
        )).all()

        print("\nPowerDevice 表设备类型:")
        for dev_type, count in sorted(power_types, key=lambda x: x[1], reverse=True):
            print(f"  {dev_type}: {count}")

        # 4. 关联关系检查
        print("\n【4】关联关系检查")
        print("-" * 80)

        # PowerDevice 有 monitor_device_id 的数量
        power_with_monitor = (await session.execute(
            select(func.count(PowerDevice.id)).where(
                PowerDevice.is_enabled == True,
                PowerDevice.monitor_device_id.isnot(None)
            )
        )).scalar()

        print(f"PowerDevice 关联 Device 的数量: {power_with_monitor}/{total_power_devices} ({power_with_monitor/total_power_devices*100:.1f}%)")

        if power_with_monitor == total_power_devices:
            print("✓ 所有 PowerDevice 都关联了 Device")
        else:
            print(f"✗ 有 {total_power_devices - power_with_monitor} 个 PowerDevice 未关联 Device")

        # 5. 特定设备验证（F1 8号UPS）
        print("\n【5】特定设备验证：F1 8号UPS")
        print("-" * 80)

        # 在 Device 表中查找
        device_result = await session.execute(
            select(Device).where(Device.device_code == "UPS-F1-08")
        )
        device = device_result.scalar_one_or_none()

        if device:
            print(f"✓ Device 表: id={device.id}, code={device.device_code}, name={device.device_name}")

            # 在 UPSDevice 表中查找
            ups_result = await session.execute(
                select(UPSDevice).where(UPSDevice.device_id == device.id)
            )
            ups = ups_result.scalar_one_or_none()
            if ups:
                print(f"✓ UPSDevice 表: id={ups.id}, device_id={ups.device_id}")
            else:
                print("✗ UPSDevice 表: 未找到")

            # 在 PowerDevice 表中查找
            pd_result = await session.execute(
                select(PowerDevice).where(PowerDevice.monitor_device_id == device.id)
            )
            pd = pd_result.scalar_one_or_none()
            if pd:
                print(f"✓ PowerDevice 表: id={pd.id}, circuit_id={pd.circuit_id}")

                if pd.circuit_id:
                    # 查找回路信息
                    circuit_result = await session.execute(
                        select(DistributionCircuit).where(DistributionCircuit.id == pd.circuit_id)
                    )
                    circuit = circuit_result.scalar_one_or_none()
                    if circuit:
                        print(f"✓ 配电回路: {circuit.circuit_code} - {circuit.circuit_name}")
                        print("✓ F1 8号UPS 应该在配电拓扑中显示")
                    else:
                        print("✗ 配电回路: 未找到")
                else:
                    print("✗ PowerDevice.circuit_id 为 NULL，不会在配电拓扑中显示")
            else:
                print("✗ PowerDevice 表: 未找到")
        else:
            print("✗ Device 表: 未找到 UPS-F1-08")

        # 6. 总结
        print("\n" + "=" * 80)
        print("验证总结")
        print("=" * 80)

        issues = []

        if device_ups_count != ups_device_count or device_ups_count != power_ups_count:
            issues.append("UPS 设备数量不一致")

        if power_ups_with_circuit != power_ups_count:
            issues.append(f"{power_ups_count - power_ups_with_circuit} 个 UPS 未绑定 circuit_id")

        if power_with_circuit != total_power_devices:
            issues.append(f"{total_power_devices - power_with_circuit} 个设备未绑定配电回路")

        if power_with_monitor != total_power_devices:
            issues.append(f"{total_power_devices - power_with_monitor} 个 PowerDevice 未关联 Device")

        if issues:
            print("\n发现以下问题:")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            print("\n建议:")
            print("  1. 停止后端服务: stop.bat")
            print("  2. 运行修复脚本: .venv\\Scripts\\python.exe scripts/fix_circuit_bindings.py")
            print("  3. 重启服务: start.bat")
        else:
            print("\n✓ 所有检查通过，数据一致性良好！")


if __name__ == "__main__":
    print("=" * 80)
    print("DCIM 数据一致性验证工具")
    print("=" * 80)
    asyncio.run(verify_consistency())
    print("=" * 80)
