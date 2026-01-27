"""Test using FastAPI's get_db dependency pattern"""
import sys
import asyncio
sys.path.insert(0, 'D:\\mytest1\\backend')

from app.api.deps import get_db
from app.api.v1.proposal import get_proposals_as_suggestions

async def test():
    # Simulate FastAPI's dependency injection
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        result = await get_proposals_as_suggestions(status=None, db=db)
        print("Success!")
        print(f"Code: {result['code']}")
        print(f"Message: {result['message']}")
        print(f"Data count: {len(result['data'])}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await db_gen.__anext__()
        except StopAsyncIteration:
            pass

if __name__ == "__main__":
    asyncio.run(test())
