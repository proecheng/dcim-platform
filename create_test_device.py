import asyncio
import sys
sys.path.insert(0, 'backend')

from app.core.database import async_session
from app.models.energy import PowerDevice

async def create_test_device():
    async with async_session() as session:
        # Create a simple test device
        device = PowerDevice(
            device_code="TEST-001",
            device_name="测试设备",
            device_type="AC",
            rated_power=50.0,
            is_enabled=True
        )
        session.add(device)
        await session.commit()
        await session.refresh(device)
        print(f"Created device: ID={device.id}, Name={device.device_name}")
        return device.id

device_id = asyncio.run(create_test_device())
print(f"\nTest device ID: {device_id}")
