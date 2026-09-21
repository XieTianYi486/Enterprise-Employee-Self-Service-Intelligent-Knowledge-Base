# ============================================================
# 通知公告模型
# 管理员发布公告，用户在聊天页顶部查看
# ============================================================

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.db.sqlite import Base


class Announcement(Base):
    """通知公告表"""
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(256), nullable=False, comment="公告标题")
    content = Column(Text, nullable=False, comment="公告内容（支持 Markdown）")
    is_published = Column(Boolean, default=True, comment="是否发布")
    created_by = Column(Integer, nullable=True, comment="发布人用户ID")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    publish_at = Column(DateTime, default=datetime.now, comment="发布时间")
    expire_at = Column(DateTime, nullable=True, comment="过期时间（可选）")