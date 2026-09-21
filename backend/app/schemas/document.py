# ============================================================
# 文档管理相关 Pydantic Schema
# ============================================================

from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    """创建分类请求"""
    name: str = Field(..., min_length=1, max_length=128, description="分类名称")
    parent_id: int = Field(default=0, description="父分类ID（0=根节点）")
    sort_order: int = Field(default=0, description="排序号")
    description: Optional[str] = Field(default=None, max_length=255, description="分类描述")


class CategoryUpdate(BaseModel):
    """更新分类请求"""
    name: Optional[str] = Field(default=None, max_length=128)
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    description: Optional[str] = Field(default=None, max_length=255)


class CategoryResponse(BaseModel):
    """分类响应"""
    id: int
    name: str
    parent_id: int
    sort_order: int
    description: Optional[str] = None
    document_count: int = Field(default=0, description="该分类下的文档数量")
    children: list["CategoryResponse"] = Field(default=[], description="子分类")
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentUpdate(BaseModel):
    """更新文档元数据"""
    title: Optional[str] = Field(default=None, max_length=255)
    category_id: Optional[int] = None
    security_level: Optional[int] = Field(default=None, ge=1, le=4)
    tags: Optional[list[str]] = None
    publish_date: Optional[date] = None
    expire_date: Optional[date] = None


class DocumentResponse(BaseModel):
    """文档响应"""
    id: int
    title: str
    file_name: str
    file_size: int
    file_type: str
    category_id: Optional[int] = None
    category_name: Optional[str] = None  # JOIN 填充
    version: str
    security_level: int
    status: int
    review_status: int = Field(default=1, description="审核状态：0草稿/1待审核/2已通过/3已驳回")
    review_comment: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    publish_date: Optional[date] = None
    expire_date: Optional[date] = None
    tags: Optional[list] = None
    chunk_count: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentVersionResponse(BaseModel):
    """文档版本响应"""
    id: int
    document_id: int
    version: str
    file_size: int
    changelog: Optional[str] = None
    archived_at: datetime

    class Config:
        from_attributes = True


class DocumentStatsResponse(BaseModel):
    """文档统计响应"""
    total_documents: int = 0
    total_chunks: int = 0
    total_size_bytes: int = 0
    by_status: dict = Field(default={}, description="按状态统计")
    by_file_type: dict = Field(default={}, description="按文件类型统计")
    by_category: dict = Field(default={}, description="按分类统计")
