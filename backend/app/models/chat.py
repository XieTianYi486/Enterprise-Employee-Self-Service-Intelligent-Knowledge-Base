# ============================================================
# SQLAlchemy 数据模型 - 会话与聊天
# 支持多轮对话、问答日志、用户反馈
# ============================================================

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, Integer, String, Text,
    DateTime, JSON, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.sqlite import Base
from app.models.user import utcnow


class ChatSession(Base):
    """
    会话表
    一个用户可以有多个会话，每个会话包含多轮对话
    """
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="会话ID（UUID 前缀）"
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID"
    )
    title: Mapped[str] = mapped_column(
        String(255), default="新对话", comment="会话标题"
    )
    message_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="消息数量"
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="最后消息时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="session",
        cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )

    def __repr__(self):
        return f"<ChatSession(id='{self.id}', title='{self.title}')>"


class ChatMessage(Base):
    """
    聊天消息表
    记录每次问答的问题和回答
    与旧项目不同：额外记录 token 使用量、耗时等性能指标
    """
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="会话ID"
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="角色：user / assistant"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="消息内容"
    )
    sources: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="引用来源（JSON 数组）"
    )
    token_count: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="消耗 token 数"
    )
    retrieval_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="检索耗时（毫秒）"
    )
    llm_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="LLM 生成耗时（毫秒）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    # 关系
    session: Mapped["ChatSession"] = relationship(
        "ChatSession", back_populates="messages"
    )

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, role='{self.role}')>"


class ChatLog(Base):
    """
    问答日志表（审计用）
    独立于消息表，记录完整的问答链路信息
    旧项目没有独立的审计日志表
    """
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="会话ID"
    )
    user_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="用户ID"
    )
    question: Mapped[str] = mapped_column(
        Text, nullable=False, comment="用户问题"
    )
    answer: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="系统回答"
    )
    source_doc_ids: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="来源文档ID列表"
    )
    feedback: Mapped[int] = mapped_column(
        Integer, default=0, comment="反馈：0=未反馈, 1=点赞, 2=点踩"
    )
    feedback_reason: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="反馈原因"
    )
    is_answered: Mapped[int] = mapped_column(
        Integer, default=1, comment="是否命中：0=未命中(拒答), 1=命中"
    )
    retrieval_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="检索耗时（毫秒）"
    )
    rerank_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="重排序耗时（毫秒）"
    )
    llm_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="LLM 生成耗时（毫秒）"
    )
    total_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="总耗时（毫秒）"
    )
    prompt_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="prompt token数"
    )
    completion_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="completion token数"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    def __repr__(self):
        return f"<ChatLog(id={self.id}, session_id='{self.session_id}')>"


