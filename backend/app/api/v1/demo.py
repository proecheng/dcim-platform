"""
演示数据API
"""
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from ...services.demo_data_service import demo_data_service

router = APIRouter(prefix="/demo", tags=["演示数据"])


class LoadDemoDataRequest(BaseModel):
    days: int = 30


class DemoDataResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


@router.get("/status")
async def get_demo_status():
    """获取演示数据状态"""
    status = await demo_data_service.check_demo_data_status()
    return {"code": 0, "data": status}


@router.post("/load")
async def load_demo_data(request: LoadDemoDataRequest, background_tasks: BackgroundTasks):
    """加载演示数据（后台任务）"""
    if demo_data_service.loading:
        return {
            "code": 1,
            "message": "正在加载中，请稍候",
            "data": {
                "progress": demo_data_service.progress,
                "progress_message": demo_data_service.progress_message
            }
        }

    # 启动后台任务
    background_tasks.add_task(demo_data_service.load_demo_data, request.days)

    return {
        "code": 0,
        "message": "开始加载演示数据",
        "data": {"days": request.days}
    }


@router.get("/progress")
async def get_load_progress():
    """获取加载进度"""
    return {
        "code": 0,
        "data": {
            "loading": demo_data_service.loading,
            "progress": demo_data_service.progress,
            "progress_message": demo_data_service.progress_message,
            "is_loaded": demo_data_service.is_loaded
        }
    }


@router.post("/unload")
async def unload_demo_data():
    """卸载演示数据"""
    result = await demo_data_service.unload_demo_data()
    return {"code": 0 if result["success"] else 1, **result}


@router.post("/refresh-dates")
async def refresh_dates(background_tasks: BackgroundTasks):
    """刷新历史数据日期到最近30天（后台任务）"""
    if demo_data_service.loading:
        return {
            "code": 1,
            "message": "正在操作中，请稍候",
            "data": {
                "progress": demo_data_service.progress,
                "progress_message": demo_data_service.progress_message
            }
        }

    # 启动后台任务
    background_tasks.add_task(demo_data_service.refresh_dates)

    return {
        "code": 0,
        "message": "开始刷新日期"
    }
