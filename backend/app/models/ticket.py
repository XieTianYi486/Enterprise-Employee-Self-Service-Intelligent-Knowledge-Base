# ============================================================
# 人工兜底工单模型
# 员工问答无法解决时一键转人工，形成工单闭环
# ============================================================

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.db.sqlite import Base
from app.models.user import utcnow


class Ticket(Base):
    """工单表：员工提问转人工处理"""

    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 关联来源
    session_id = Column(String(64), nullable=True, comment="来源会话ID（可选）")
    created_by = Column(Integer, nullable=False, index=True, comment="提交人用户ID")
    handler_id = Column(Integer, nullable=True, comment="处理人用户ID")

    # 内容
    title = Column(String(256), nullable=False, comment="工单标题")
    question = Column(Text, nullable=False, comment="用户原始问题")
    detail = Column(Text, nullable=True, comment="补充说明")

    # 状态流转：pending=待处理 processing=处理中 resolved=已解决 closed=已关闭
    status = Column(String(20), default="pending", nullable=False, index=True, comment="工单状态")
    priority = Column(String(10), default="medium", nullable=False, comment="优先级：high/medium/low")

    # 人工回复
    reply = Column(Text, nullable=True, comment="处理人回复")
    reply_count = Column(Integer, default=0, comment="回复次数")

    created_at = Column(DateTime, default=utcnow, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, comment="更新时间")
    resolved_at = Column(DateTime, nullable=True, comment="解决时间")