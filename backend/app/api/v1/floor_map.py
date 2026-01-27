"""楼层图 API"""
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, distinct
from pydantic import BaseModel

from ..deps import get_db, get_current_user
from ...models import FloorMap
from ...models.user import User
from ...schemas.common import ResponseModel

router = APIRouter()


class FloorInfo(BaseModel):
    """楼层信息"""
    floor_code: str
    floor_name: str
    map_types: List[str]


class FloorListResponse(BaseModel):
    """楼层列表响应"""
    floors: List[FloorInfo]


class FloorMapResponse(BaseModel):
    """楼层图响应"""
    id: int
    floor_code: str
    floor_name: str
    map_type: str
    map_data: dict
    thumbnail: Optional[str] = None
    is_default: bool

    class Config:
        from_attributes = True


@router.get("/floors", response_model=ResponseModel[FloorListResponse], summary="获取楼层列表")
async def get_floors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有楼层及其可用的图类型"""
    result = await db.execute(
        select(FloorMap.floor_code, FloorMap.floor_name, FloorMap.map_type)
        .order_by(FloorMap.floor_code, FloorMap.map_type)
    )
    rows = result.fetchall()

    # 按楼层分组
    floor_dict = {}
    for row in rows:
        code = row[0]
        if code not in floor_dict:
            floor_dict[code] = {
                "floor_code": code,
                "floor_name": row[1],
                "map_types": []
            }
        if row[2] not in floor_dict[code]["map_types"]:
            floor_dict[code]["map_types"].append(row[2])

    # 按楼层排序 (B1, F1, F2, F3)
    sorted_floors = sorted(floor_dict.values(), key=lambda x: (
        0 if x["floor_code"].startswith("B") else 1,
        x["floor_code"]
    ))

    floors = [FloorInfo(**f) for f in sorted_floors]
    return ResponseModel(data=FloorListResponse(floors=floors))


@router.get("/{floor_code}/{map_type}", response_model=ResponseModel[FloorMapResponse], summary="获取楼层图")
async def get_floor_map(
    floor_code: str,
    map_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定楼层的2D或3D图数据"""
    if map_type not in ["2d", "3d"]:
        raise HTTPException(status_code=400, detail="Invalid map type. Must be '2d' or '3d'")

    result = await db.execute(
        select(FloorMap).where(
            FloorMap.floor_code == floor_code.upper(),
            FloorMap.map_type == map_type
        )
    )
    floor_map = result.scalar_one_or_none()

    if not floor_map:
        raise HTTPException(status_code=404, detail=f"Floor map not found: {floor_code}/{map_type}")

    response = FloorMapResponse(
        id=floor_map.id,
        floor_code=floor_map.floor_code,
        floor_name=floor_map.floor_name,
        map_type=floor_map.map_type,
        map_data=json.loads(floor_map.map_data),
        thumbnail=floor_map.thumbnail,
        is_default=floor_map.is_default
    )

    return ResponseModel(data=response)


@router.get("/default", response_model=ResponseModel[FloorMapResponse], summary="获取默认楼层图")
async def get_default_floor_map(
    map_type: str = "3d",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取默认显示的楼层图"""
    # 先找标记为默认的
    result = await db.execute(
        select(FloorMap).where(
            FloorMap.is_default == True,
            FloorMap.map_type == map_type
        )
    )
    floor_map = result.scalar_one_or_none()

    # 没有默认的就取F1
    if not floor_map:
        result = await db.execute(
            select(FloorMap).where(
                FloorMap.floor_code == "F1",
                FloorMap.map_type == map_type
            )
        )
        floor_map = result.scalar_one_or_none()

    if not floor_map:
        raise HTTPException(status_code=404, detail="No floor map available")

    response = FloorMapResponse(
        id=floor_map.id,
        floor_code=floor_map.floor_code,
        floor_name=floor_map.floor_name,
        map_type=floor_map.map_type,
        map_data=json.loads(floor_map.map_data),
        thumbnail=floor_map.thumbnail,
        is_default=floor_map.is_default
    )

    return ResponseModel(data=response)
