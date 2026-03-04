import asyncio
import sys
sys.path.insert(0, 'backend')

from app.core.database import async_session
from app.services.device_regulation_service import DeviceRegulationService

async def test():
    async with async_session() as session:
        service = DeviceRegulationService(session)
        result = await service.get_device_power_trend(1, 30)
        print(f"Result type: {type(result)}")
        print(f"Result: {result}")

asyncio.run(test())
