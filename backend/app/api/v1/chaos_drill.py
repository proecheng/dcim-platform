"""
Chaos Drill API - Story 26.7
灾难恢复演练管理
"""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import require_role
from app.models.log import OperationLog
from app.models.user import User
from app.schemas.chaos_drill import (
    DrillScheduleResponse,
    DrillScheduleUpdateRequest,
    DrillTriggerRequest,
    DrillTriggerResponse,
    DrillStopResponse,
    DrillHistoryResponse,
    DrillHistoryItem,
)
from app.services.diagnosis.chaos_drill_service import ChaosDrillService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnosis/chaos", tags=["灾难恢复演练"])


def _get_breaker():
    """尝试获取调度器的 CircuitBreaker 实例"""
    try:
        from app.services.diagnosis.scheduler import _scheduler

        if _scheduler and hasattr(_scheduler, "circuit_breaker"):
            return _scheduler.circuit_breaker
    except Exception:
        pass
    return None


@router.get("/schedule", response_model=DrillScheduleResponse, dependencies=[Depends(require_role(["admin"]))])
async def get_drill_schedule(db: AsyncSession = Depends(get_db)):
    """获取演练计划配置"""
    service = ChaosDrillService(db)
    schedule = await service.get_drill_schedule()
    return DrillScheduleResponse(**schedule)


@router.put("/schedule", response_model=DrillScheduleResponse, dependencies=[Depends(require_role(["admin"]))])
async def update_drill_schedule(
    request: DrillScheduleUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """更新演练计划"""
    service = ChaosDrillService(db)
    try:
        schedule = await service.update_drill_schedule(request.model_dump(exclude_none=True))
        return DrillScheduleResponse(**schedule)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/schedule/confirm")
async def confirm_drill_schedule(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["admin"])),
):
    """确认演练计划"""
    service = ChaosDrillService(db)
    try:
        await service.confirm_drill_schedule(user_id=current_user.id)
        return {"message": "演练计划已确认"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/trigger", response_model=DrillTriggerResponse, status_code=202)
async def trigger_drill(
    request: DrillTriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """手动触发演练"""
    service = ChaosDrillService(db)
    breaker = _get_breaker()

    try:
        drill_id = await service.trigger_drill(
            scenarios=request.scenarios,
            breaker=breaker,
        )

        # 审计日志
        db.add(
            OperationLog(
                user_id=current_user.id,
                username=current_user.username,
                module="chaos_drill",
                action="trigger_drill",
                target_type="drill",
                target_id=drill_id,
                new_value=json.dumps({"scenarios": request.scenarios}, ensure_ascii=False),
            )
        )
        await db.commit()

        return DrillTriggerResponse(message="演练已启动", drill_id=drill_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stop", response_model=DrillStopResponse)
async def stop_drill(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """终止演练"""
    service = ChaosDrillService(db)
    breaker = _get_breaker()

    try:
        drill_id = await service.stop_drill(breaker=breaker)

        # 审计日志
        db.add(
            OperationLog(
                user_id=current_user.id,
                username=current_user.username,
                module="chaos_drill",
                action="stop_drill",
                target_type="drill",
                target_id=drill_id,
            )
        )
        await db.commit()

        return DrillStopResponse(
            message="演练已终止，所有故障已恢复",
            drill_id=drill_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history", response_model=DrillHistoryResponse, dependencies=[Depends(require_role(["admin"]))])
async def get_drill_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """查询演练历史"""
    service = ChaosDrillService(db)
    result = await service.get_drill_history(page=page, page_size=page_size)

    items = [DrillHistoryItem.model_validate(r) for r in result["items"]]
    return DrillHistoryResponse(total=result["total"], items=items)
