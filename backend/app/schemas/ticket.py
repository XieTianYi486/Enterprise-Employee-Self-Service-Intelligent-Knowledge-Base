# ============================================================
# 工单相关 Pydantic Schema
# ============================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TicketCreateRequest(BaseModel):
    """创建工单请求（员工）"""
    title: str = Field(..., min_length=1, max_length=256, description="工单标题")
    question: str = Field(..., min_length=1, description="原始问题")
    detail: Optional[str] = Field(default=None, max_length=2000, description="补充说明")
    session_id: Optional[str] = Field(default=None, max_length=64, description="关联会话ID")
    priority: str = Field(default="medium", description="优先级：high/medium/low")


class TicketReplyRequest(BaseModel):
    """处理工单请求（管理员）"""
    reply: str = Field(..., min_length=1, max_length=5000, description="处理回复")


class TicketStatusRequest(BaseModel):
    """更新工单状态请求（管理员）"""
    status: str = Field(..., description="状态：pending/processing/resolved/closed")


class TicketInfo(BaseModel):
    """工单信息响应"""
    id: int
    title: str
    question: str
    detail: Optional[str] = None
    status: str
    priority: str
    reply: Optional[str] = None
    reply_count: int
    session_id: Optional[str] = None
    created_by: int
    handler_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    # 关联显示字段（由 JOIN 填充）
    creator_name: Optional[str] = None
    handler_name: Optional[str] = None

    class Config:
        from_attributes = True