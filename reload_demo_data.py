"""清理旧演示数据并重新加载"""
import asyncio
import sys
sys.path.insert(0, 'backend')

from app.demo.service import DemoDataService

async def reload_demo_data():
    """清理并重新加载演示数据"""
    service = DemoDataService()
    
    print("=" * 60)
    print("清理旧演示数据并重新加载（使用新配置）")
    print("=" * 60)
    print()
    
    # 1. 检查当前状态
    print("步骤 1/3: 检查当前状态...")
    status = await service.check_demo_data_status()
    print(f"  当前点位数: {status['demo_point_count']}")
    print(f"  历史记录数: {status['history_count']:,}")
    print()
    
    # 2. 卸载旧数据
    if status['demo_point_count'] > 0:
        print("步骤 2/3: 卸载旧演示数据...")
        result = await service.unload_demo_data()
        if result['success']:
            print(f"  ✓ 卸载成功")
        else:
            print(f"  ✗ 卸载失败: {result.get('message')}")
            return
    else:
        print("步骤 2/3: 跳过（无旧数据）")
    print()
    
    # 3. 加载新数据（使用新配置）
    print("步骤 3/3: 加载新演示数据...")
    print("  配置: collect_interval=60s, store_interval=300s")
    print("  预计时间: 2-3 分钟")
    print()
    
    def progress_callback(progress: int, message: str):
        print(f"  [{progress:3d}%] {message}")
    
    result = await service.load_demo_data(days=30, progress_callback=progress_callback)
    
    print()
    if result['success']:
        print("✅ 演示数据加载完成！")
        print(f"  点位数: {result['point_count']}")
        print(f"  历史记录数: {result['history_count']:,}")
        print(f"  天数: {result['days']}")
    else:
        print(f"✗ 加载失败: {result.get('message')}")

if __name__ == "__main__":
    asyncio.run(reload_demo_data())
