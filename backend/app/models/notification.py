# ============================================================
# SQLAlchemy 数据模型 - 站内消息
# 触发场景：审批结果通知（申请人）、工单回复通知（提交人）、
#          公告发布通知等
# ============================================================

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.sqlite import Base
from app.models.user import utcnow


class Notification(Base):
    """站内消息表"""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="接收人ID"
    )
    type: Mapped[str] = mapped_column(
        String(32), default="SYSTEM", comment="消息类型 APPROVAL/TICKET/ANNOUNCEMENT/SYSTEM"
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False, comment="消息标题")
    content: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="消息内容"
    )
    biz_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="关联业务类型（LEAVE/EXPENSE/TICKET）"
    )
    biz_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="关联业务ID"
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="是否已读"
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, type='{self.type}')>"
