import sys
sys.path.insert(0, 'D:/mytest1/backend')

try:
    from app.services.device_regulation_service import DeviceRegulationService
    print("导入成功")
except Exception as e:
    print(f"导入失败: {e}")
    import traceback
    traceback.print_exc()
