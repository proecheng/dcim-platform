import sys
content = open("app/api/v1/energy.py", "r", encoding="utf-8").read()

new_endpoint = """
@router.get(
    "/devices/{device_id}/power-trend", 
    response_model=ResponseModel[Dict[str, Any]], 
    summary="获取设备功率趋势曲线"
)
async def get_device_power_trend(
    device_id: int,
    days: int = Query(30, ge=7, le=90, description="分析历史数据天数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    \"\"\"
    获取指定设备的功率趋势曲线（按天聚合）
    
    返回每天的平均/最大/最小功率，用于 30/90 天趋势图展示
    \"\"\"
    from ...services.device_regulation_service import DeviceRegulationService
    
    service = DeviceRegulationService(db)
    result = await service.get_device_power_trend(device_id, days)
    if not result:
        raise HTTPException(status_code=404, detail=f"设备 {device_id} 不存在")
    return ResponseModel(data=result)

"""

if "power-trend" not in content:
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "update_device_shift_ratio" in line and "@router" in line:
            lines.insert(i, new_endpoint)
            break
    
    open("app/api/v1/energy.py", "w", encoding="utf-8").write('\n'.join(lines))
    print("Added get_device_power_trend to energy.py")
else:
    print("Endpoint already exists")
