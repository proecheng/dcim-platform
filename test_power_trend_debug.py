import asyncio
import sys
sys.path.insert(0, 'backend')

from app.core.database import async_session
from app.services.device_regulation_service import DeviceRegulationService

async def test():
    async with async_session() as session:
        service = DeviceRegulationService(session)
        try:
            result = await service.get_device_power_trend(9, 30)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

asyncio.run(test())
