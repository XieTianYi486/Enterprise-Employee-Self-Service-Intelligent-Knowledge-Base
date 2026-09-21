# ============================================================
# 通用 Pydantic Schema
# 统一响应格式、分页
# ============================================================

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel):
    """
    统一 API 响应格式
    所有接口返回此结构
    """
    code: int = Field(default=0, description="状态码，0=成功，非0=失败")
    message: str = Field(default="success", description="提示信息")
    data: Any = Field(default=None, description="响应数据")

    class Config:
        json_schema_extra = {
            "example": {
                "code": 0,
                "message": "success",
                "data": {}
            }
        }


class PaginationParams(BaseModel):
    """分页查询参数"""
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class PaginatedData(BaseModel, Generic[T]):
    """分页响应数据"""
    items: list[T] = Field(default=[], description="数据列表")
    total: int = Field(default=0, description="总记录数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")
    total_pages: int = Field(default=0, description="总页数")

    @classmethod
    def from_query(cls, items: list[T], total: int, page: int, page_size: int):
        """便捷构造分页响应"""
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
