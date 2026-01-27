"""
通用响应模型
"""
from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel
from datetime import datetime

T = TypeVar("T")


class PageParams(BaseModel):
    """分页参数"""
    page: int = 1
    page_size: int = 20


class PageResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: List[T]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size if self.page_size > 0 else 0


class ResponseModel(BaseModel, Generic[T]):
    """标准响应模型"""
    code: int = 0
    message: str = "success"
    data: Optional[T] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    code: int
    message: str
    detail: Optional[str] = None


class SuccessResponse(BaseModel):
    """成功响应"""
    message: str = "操作成功"
