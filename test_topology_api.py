"""
测试拓扑编辑 API
"""
import asyncio
import sys
sys.path.insert(0, 'D:/mytest1/backend')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.services.energy_topology import EnergyTopologyService
from app.schemas.energy import TopologyNodeCreate, TopologyNodeType, TopologyNodeUpdate

# 数据库连接
DATABASE_URL = "sqlite+aiosqlite:///D:/mytest1/backend/dcim.db"
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def test_export():
    """测试导出功能"""
    print("=" * 60)
    print("测试导出拓扑")
    print("=" * 60)
    async with async_session_maker() as db:
        try:
            result = await EnergyTopologyService.export_topology(db)
            print(f"[OK] 导出成功")
            print(f"  - 变压器: {len(result.transformers)}")
            print(f"  - 计量点: {len(result.meter_points)}")
            print(f"  - 配电柜: {len(result.panels)}")
            print(f"  - 回路: {len(result.circuits)}")
            print(f"  - 设备: {len(result.devices)}")
            return True
        except Exception as e:
            print(f"[FAIL] 导出失败: {e}")
            import traceback
            traceback.print_exc()
            return False

async def test_create_transformer():
    """测试创建变压器"""
    print("\n" + "=" * 60)
    print("测试创建变压器")
    print("=" * 60)
    async with async_session_maker() as db:
        try:
            create_data = TopologyNodeCreate(
                node_type=TopologyNodeType.TRANSFORMER,
                transformer_code="T001",
                transformer_name="1#变压器",
                rated_capacity=1000,
                voltage_high=10,
                voltage_low=400
            )
            node_id, node_type = await EnergyTopologyService.create_node(db, create_data)
            await db.commit()
            print(f"[OK] 创建成功: ID={node_id}, Type={node_type}")
            return node_id
        except Exception as e:
            await db.rollback()
            print(f"[FAIL] 创建失败: {e}")
            import traceback
            traceback.print_exc()
            return None

async def test_update_transformer(transformer_id):
    """测试更新变压器"""
    print("\n" + "=" * 60)
    print("测试更新变压器")
    print("=" * 60)
    async with async_session_maker() as db:
        try:
            update_data = TopologyNodeUpdate(
                node_id=transformer_id,
                node_type=TopologyNodeType.TRANSFORMER,
                name="1#主变压器(已更新)",
                location="A区机房"
            )
            success = await EnergyTopologyService.update_node(db, update_data)
            await db.commit()
            if success:
                print(f"[OK] 更新成功")
            else:
                print(f"[FAIL] 更新失败: 节点不存在")
            return success
        except Exception as e:
            await db.rollback()
            print(f"[FAIL] 更新失败: {e}")
            import traceback
            traceback.print_exc()
            return False

async def test_create_meter_point(transformer_id):
    """测试创建计量点"""
    print("\n" + "=" * 60)
    print("测试创建计量点")
    print("=" * 60)
    async with async_session_maker() as db:
        try:
            create_data = TopologyNodeCreate(
                node_type=TopologyNodeType.METER_POINT,
                parent_id=transformer_id,
                parent_type=TopologyNodeType.TRANSFORMER,
                meter_code="M001",
                meter_name="总表",
                ct_ratio=100,
                pt_ratio=10
            )
            node_id, node_type = await EnergyTopologyService.create_node(db, create_data)
            await db.commit()
            print(f"[OK] 创建成功: ID={node_id}, Type={node_type}")
            return node_id
        except Exception as e:
            await db.rollback()
            print(f"[FAIL] 创建失败: {e}")
            import traceback
            traceback.print_exc()
            return None

async def main():
    print("\n" + "="*60)
    print("拓扑编辑功能测试")
    print("="*60)

    # 测试导出（空数据）
    await test_export()

    # 测试创建变压器
    transformer_id = await test_create_transformer()
    if transformer_id:
        # 测试更新变压器
        await test_update_transformer(transformer_id)

        # 测试创建计量点
        meter_point_id = await test_create_meter_point(transformer_id)

        # 再次测试导出
        print("\n" + "=" * 60)
        print("再次测试导出（有数据）")
        print("=" * 60)
        await test_export()

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
