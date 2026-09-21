# ============================================================
# SQLAlchemy 数据模型 - 用户与角色
# 完整 RBAC 权限模型（旧项目仅有二元 admin/user 区分）
# ============================================================

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column, Integer, Integer, String, Text, Boolean,
    DateTime, Float, Date, JSON, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.sqlite import Base


def utcnow():
    """返回当前 UTC 时间"""
    return datetime.now(timezone.utc)


class Role(Base):
    """
    角色表
    预置角色：super_admin, knowledge_admin, dept_admin, employee
    """
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="角色名称")
    code: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, comment="角色编码"
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="角色描述"
    )
    permissions: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="权限点列表（JSON 数组）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    # 关系
    users: Mapped[list["User"]] = relationship("User", back_populates="role")

    def __repr__(self):
        return f"<Role(id={self.id}, code='{self.code}')>"


class User(Base):
    """
    用户表
    关联角色，支持部门归属
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True, comment="用户名"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希（bcrypt）"
    )
    real_name: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="真实姓名"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="邮箱"
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="手机号"
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="头像 URL"
    )
    position: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="职位"
    )
    # 部门以 dept_id 外键为准（历史 department 字符串列保留在库中但不再映射）
    dept_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id"), nullable=True, index=True, comment="所属部门ID"
    )
    gender: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True, default="男", comment="性别（男/女）"
    )
    entry_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="入职日期"
    )
    role_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("roles.id"), nullable=False, default=1, comment="角色ID"
    )
    status: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="状态：0=禁用, 1=正常"
    )
    # ===== 登录安全字段 =====
    failed_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="连续登录失败次数"
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="账号锁定截止时间（NULL=未锁定）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    # 关系
    role: Mapped["Role"] = relationship("Role", back_populates="users")
    dept: Mapped[Optional["Department"]] = relationship("Department", foreign_keys=[dept_id])
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        "ChatSession", back_populates="user"
    )

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Department(Base):
    """
    部门表
    管理部门元数据（名称、负责人、描述），User.dept_id 外键关联
    """
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, comment="部门名称"
    )
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="部门负责人ID"
    )
    parent_id: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="上级部门ID（0=顶级）"
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="部门描述"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="排序号"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    def __repr__(self):
        return f"<Department(id={self.id}, name='{self.name}')>"
