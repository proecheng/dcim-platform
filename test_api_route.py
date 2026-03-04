import asyncio
import sys
sys.path.insert(0, 'backend')

from app.core.database import async_session
from app.api.v1.energy import get_device_power_trend
from app.models.user import User

async def test():
    # Create a mock user
    user = User(id=1, username="admin", role="admin")
    
    async with async_session() as session:
        try:
            result = await get_device_power_trend(
                device_id=1,
                days=30,
                db=session,
                current_user=user
            )
            print(f"API result: {result}")
            print(f"Result type: {type(result)}")
        except Exception as e:
            print(f"Exception: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

asyncio.run(test())
