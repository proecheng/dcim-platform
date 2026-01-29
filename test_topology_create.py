"""
测试拓扑节点创建 API - 直接调用服务层
"""
import asyncio
import sys
sys.path.insert(0, 'D:/mytest1/backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.energy_topology import EnergyTopologyService
from app.schemas.energy import TopologyNodeCreate, TopologyNodeType

# 数据库连接
DATABASE_URL = "sqlite+aiosqlite:///D:/mytest1/backend/dcim.db"
engine = create_async_engine(DATABASE_URL, echo=True)  # echo=True显示SQL
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def test_create_device():
    """测试创建设备 - 模拟前端请求"""
    print("=" * 60)
    print("测试创建设备节点 (模拟前端请求)")
    print("=" * 60)

    async with async_session_maker() as db:
        try:
            # 模拟前端发送的数据
            create_data = TopologyNodeCreate(
                node_type=TopologyNodeType.DEVICE,
                device_code="DEV-999",
                device_name="测试设备999",
                device_type="IT",
                rated_power=10.0,
                parent_id=1,  # 假设有回路ID=1
                parent_type=TopologyNodeType.CIRCUIT
            )

            print(f"创建数据: {create_data}")
            print(f"  - node_type: {create_data.node_type}")
            print(f"  - device_code: {create_data.device_code}")
            print(f"  - device_name: {create_data.device_name}")
            print(f"  - device_type: {create_data.device_type}")
            print(f"  - rated_power: {create_data.rated_power}")
            print(f"  - parent_id: {create_data.parent_id}")
            print(f"  - parent_type: {create_data.parent_type}")

            # 调用服务层
            node_id, node_type = await EnergyTopologyService.create_node(db, create_data)
            await db.commit()

            print(f"\n[SUCCESS] 创建成功!")
            print(f"  - node_id: {node_id}")
            print(f"  - node_type: {node_type}")
            return True

        except Exception as e:
            await db.rollback()
            print(f"\n[FAIL] 创建失败: {e}")
            import traceback
            traceback.print_exc()
            return False

async def test_create_transformer():
    """测试创建变压器 - 使用新编码避免冲突"""
    print("\n" + "=" * 60)
    print("测试创建变压器节点")
    print("=" * 60)

    async with async_session_maker() as db:
        try:
            import random
            code = f"TR-{random.randint(100, 999)}"

            create_data = TopologyNodeCreate(
                node_type=TopologyNodeType.TRANSFORMER,
                transformer_code=code,
                transformer_name=f"测试变压器{code}",
                rated_capacity=1000.0,
                voltage_high=10.0,
                voltage_low=0.4
            )

            print(f"创建数据: transformer_code={code}")

            node_id, node_type = await EnergyTopologyService.create_node(db, create_data)
            await db.commit()

            print(f"\n[SUCCESS] 创建成功!")
            print(f"  - node_id: {node_id}")
            print(f"  - node_type: {node_type}")
            return True

        except Exception as e:
            await db.rollback()
            print(f"\n[FAIL] 创建失败: {e}")
            import traceback
            traceback.print_exc()
            return False

async def main():
    print("开始测试拓扑节点创建...\n")

    # 测试创建变压器
    result1 = await test_create_transformer()

    # 测试创建设备
    result2 = await test_create_device()

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"创建变压器: {'通过' if result1 else '失败'}")
    print(f"创建设备: {'通过' if result2 else '失败'}")

if __name__ == "__main__":
    asyncio.run(main())
