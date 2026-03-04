"""
直接测试 get_device_power_trend 函数
"""
import sys
sys.path.insert(0, 'D:/mytest1/backend')

import asyncio
from app.core.database import async_session
from app.services.device_regulation_service import DeviceRegulationService

async def test():
    async with async_session() as db:
        service = DeviceRegulationService(db)
        try:
            result = await service.get_device_power_trend(9, 30)
            if result:
                print("成功!")
                print(f"设备: {result['device_name']}")
                print(f"天数: {result['days']}")
                print(f"趋势数据条数: {len(result['trend_data'])}")
                if result['trend_data']:
                    print(f"第一条: {result['trend_data'][0]}")
            else:
                print("设备不存在")
        except Exception as e:
            print(f"错误: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test())
