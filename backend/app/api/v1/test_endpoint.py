from fastapi import APIRouter

router = APIRouter()

@router.get("/test-simple")
async def test_simple():
    """Simple test endpoint"""
    return {"message": "Hello from test endpoint"}
