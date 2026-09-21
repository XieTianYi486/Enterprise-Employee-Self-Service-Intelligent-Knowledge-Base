# ============================================================
# SQLAlchemy 数据模型 - 操作审计日志 / 敏感词
# 合规：登录、敏感词命中、文档审核、数据导出等关键操作留痕
# ============================================================

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.sqlite import Base
from app.models.user import utcnow


class AuditLog(Base):
    """
    审计日志表

    记录所有需要留痕的关键操作：
    - 登录成功/失败/锁定
    - 敏感词命中（问答脱敏、检索拦截）
    - 文档审核（通过/驳回）
    - 数据导出、删除等高风险操作
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="操作用户ID"
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="操作用户名"
    )
    module: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
        comment="模块：login/security/sensitive/document/chat/admin"
    )
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="操作动作，如 login_success / sensitive_hit"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="success", nullable=False,
        comment="结果：success/failure/blocked"
    )
    target_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="目标类型：document/word/user"
    )
    target_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="目标ID"
    )
    detail: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="附加信息（JSON）"
    )
    ip: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="客户端IP"
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="客户端 UA"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, module='{self.module}', action='{self.action}')>"


class SensitiveWord(Base):
    """
    敏感词表

    用于问答回答脱敏与检索拦截：
    - level=1 提示级：仅记录不做处理
    - level=2 拦截级：命中时用 replacement 替换（脱敏）
    - level=3 高危级：命中即拒绝回答 / 拦截管理操作
    """
    __tablename__ = "sensitive_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True, comment="敏感词"
    )
    category: Mapped[str] = mapped_column(
        String(32), default="general", nullable=False, comment="分类：general/security/pii"
    )
    level: Mapped[int] = mapped_column(
        Integer, default=2, nullable=False,
        comment="级别：1=提示, 2=拦截脱敏, 3=高危(拒答)"
    )
    action: Mapped[str] = mapped_column(
        String(16), default="mask", nullable=False, comment="动作：mask=替换, block=拒答"
    )
    replacement: Mapped[str] = mapped_column(
        String(32), default="***", nullable=False, comment="脱敏替换串"
    )
    enabled: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="是否启用：0=停用, 1=启用"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    def __repr__(self):
        return f"<SensitiveWord(id={self.id}, word='{self.word}')>"