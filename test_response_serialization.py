import sys
sys.path.insert(0, 'backend')

from typing import Dict, Any
from app.schemas.common import ResponseModel

# Test data from service
test_data = {
    'device_id': 1,
    'device_name': 'Test Device',
    'device_type': 'AC',
    'rated_power': 50.0,
    'daily_data': []
}

try:
    # Test with generic type
    response = ResponseModel[Dict[str, Any]](data=test_data)
    print("OK: ResponseModel[Dict[str, Any]] created successfully")
    print(f"Response JSON: {response.model_dump_json()}")
except Exception as e:
    print(f"ERROR with ResponseModel[Dict[str, Any]]: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

try:
    # Test without generic type
    response2 = ResponseModel(data=test_data)
    print("\nOK: ResponseModel (no generic) created successfully")
    print(f"Response JSON: {response2.model_dump_json()}")
except Exception as e:
    print(f"\nERROR with ResponseModel (no generic): {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
