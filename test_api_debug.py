import requests
import json

# 登录
login_resp = requests.post(
    "http://localhost:8080/api/v1/auth/login",
    data={"username": "admin", "password": "admin123"}
)
token = login_resp.json()["access_token"]
print(f"Token: {token[:50]}...")

# 测试 API
headers = {"Authorization": f"Bearer {token}"}
resp = requests.get(
    "http://localhost:8080/api/v1/energy/devices/9/power-trend?days=30",
    headers=headers
)

print(f"\nStatus: {resp.status_code}")
print(f"Response: {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
