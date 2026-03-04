import sys
sys.path.insert(0, 'backend')

from app.schemas.common import ResponseModel

# Test data from service
test_data = {
    'device_id': 1,
    'device_name': '测试设备',
    'device_type': 'AC',
    'rated_power': 50.0,
    'daily_data': []
}

try:
    response = ResponseModel(data=test_data)
    print(f"ResponseModel created successfully")
    print(f"Response: {response}")
    print(f"Response dict: {response.model_dump()}")
    print(f"Response JSON: {response.model_dump_json()}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
