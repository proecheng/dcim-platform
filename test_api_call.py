"""
直接测试 API 调用
"""
import requests
import json

url = "http://localhost:8080/api/v1/topology/nodes"

data = {
    "node_type": "device",
    "device_code": "TEST-API-001",
    "device_name": "API测试设备",
    "device_type": "IT",
    "rated_power": 10,
    "parent_id": 1,
    "parent_type": "circuit"
}

print("请求URL:", url)
print("请求数据:", json.dumps(data, ensure_ascii=False, indent=2))
print()

try:
    response = requests.post(url, json=data)
    print("状态码:", response.status_code)
    print("响应头:", dict(response.headers))
    print("响应内容:", response.text)
except Exception as e:
    print("请求失败:", e)
