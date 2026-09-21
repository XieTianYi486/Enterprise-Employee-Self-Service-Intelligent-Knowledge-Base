# ============================================================
# 问答聊天相关 Pydantic Schema
# ============================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CitationSource(BaseModel):
    """引用来源"""
    document_id: int
    document_name: str
    chapter: Optional[str] = None
    page: Optional[int] = None
    snippet: str = Field(..., description="引用片段")
    score: float = Field(..., description="相关性分数")


class AskRequest(BaseModel):
    """提问请求"""
    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    session_id: Optional[str] = Field(default=None, description="会话ID（新对话可为空）")
    category_ids: Optional[list[int]] = Field(
        default=None, description="限定分类范围（可选）"
    )
    document_ids: Optional[list[int]] = Field(
        default=None, description="限定文档范围（可选）"
    )


class AskResponse(BaseModel):
    """非流式问答响应"""
    answer_id: str = Field(..., description="回答ID")
    answer: str = Field(..., description="回答内容")
    sources: list[CitationSource] = Field(default=[], description="引用来源")
    session_id: str = Field(..., description="会话ID")
    usage: dict = Field(default={}, description="Token 用量信息")
    latency: dict = Field(default={}, description="各阶段耗时信息")


class FeedbackRequest(BaseModel):
    """答案反馈请求"""
    message_id: Optional[int] = Field(default=None, description="消息ID")
    session_id: Optional[str] = Field(default=None, description="会话ID（用于关联日志）")
    feedback: int = Field(..., ge=0, le=2, description="0=取消, 1=点赞, 2=点踩")
    reason: Optional[str] = Field(default=None, max_length=255, description="反馈原因")


class SessionCreate(BaseModel):
    """创建会话请求"""
    title: str = Field(default="新对话", max_length=255)


class SessionUpdate(BaseModel):
    """更新会话请求"""
    title: Optional[str] = Field(default=None, max_length=255)


class SessionResponse(BaseModel):
    """会话响应"""
    id: str
    user_id: int
    title: str
    message_count: int
    last_message_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """消息响应"""
    id: int
    session_id: str
    role: str
    content: str
    sources: Optional[list[CitationSource]] = None
    token_count: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
