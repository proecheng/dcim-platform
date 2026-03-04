import asyncio
import sys
sys.path.insert(0, 'backend')

from app.core.database import async_session
from app.services.device_regulation_service import DeviceRegulationService

async def test():
    async with async_session() as session:
        service = DeviceRegulationService(session)
        try:
            print("Testing device_id=9...")
            result = await service.get_device_power_trend(9, 30)
            print(f"Result: {result}")
            
            # Test with a device that might exist
            print("\nChecking if any devices exist...")
            from app.models.energy import PowerDevice
            from sqlalchemy import select
            devices_result = await session.execute(select(PowerDevice).limit(5))
            devices = devices_result.scalars().all()
            print(f"Found {len(devices)} devices")
            
            if devices:
                print(f"\nTesting with device_id={devices[0].id}...")
                result2 = await service.get_device_power_trend(devices[0].id, 30)
                print(f"Result: {result2}")
        except Exception as e:
            print(f"Exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

asyncio.run(test())
