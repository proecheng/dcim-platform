"""Test the as-suggestions endpoint directly"""
import sys
import asyncio
sys.path.insert(0, 'D:\\mytest1\\backend')

from app.core.database import async_session
from app.api.v1.proposal import get_proposals_as_suggestions

async def test():
    async with async_session() as db:
        try:
            result = await get_proposals_as_suggestions(status=None, db=db)
            print("Success!")
            print(f"Code: {result['code']}")
            print(f"Message: {result['message']}")
            print(f"Data count: {len(result['data'])}")
            if result['data']:
                print(f"First item: {result['data'][0]}")
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
