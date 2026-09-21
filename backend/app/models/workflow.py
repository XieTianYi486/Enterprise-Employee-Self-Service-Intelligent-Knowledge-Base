# ============================================================
# SQLAlchemy 数据模型 - OA 办公流程
# 请假 / 报销 / 假期余额 / 审批流水
#
# 审批状态机：
#   PENDING（待审批）→ APPROVED（已通过）/ REJECTED（已驳回）
#   PENDING → CANCELLED（已撤销，仅申请人本人可撤）
# 审批节点：
#   MANAGER（部门经理）→ BOSS（总经理，超阈值升级）；NONE（免审/流程结束）
# ============================================================

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.sqlite import Base
from app.models.user import utcnow


class LeaveBalance(Base):
    """
    假期余额表
    按「员工 + 年份」各一条记录；审批通过后按假期类型扣减对应额度
    """
    __tablename__ = "leave_balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="员工ID"
    )
    year: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="年份"
    )
    annual_total: Mapped[float] = mapped_column(
        Float, default=5.0, nullable=False, comment="年假总额（天）"
    )
    annual_used: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False, comment="已用年假（天）"
    )
    personal_used: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False, comment="已用事假（天）"
    )
    sick_used: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False, comment="已用病假（天）"
    )
    compensatory_total: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False, comment="调休总额（天）"
    )
    compensatory_used: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False, comment="已用调休（天）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    def __repr__(self):
        return f"<LeaveBalance(user_id={self.user_id}, year={self.year})>"


class LeaveRequest(Base):
    """
    请假单表
    leave_type: 年假/事假/病假/调休/婚假
    status: PENDING/APPROVED/REJECTED/CANCELLED
    current_node: MANAGER/BOSS/NONE
    """
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="申请人ID"
    )
    dept_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="申请人部门ID（提交时快照）"
    )
    leave_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="请假类型"
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, comment="开始日期")
    end_date: Mapped[date] = mapped_column(Date, nullable=False, comment="结束日期")
    days: Mapped[float] = mapped_column(Float, nullable=False, comment="请假天数")
    reason: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="请假事由"
    )
    status: Mapped[str] = mapped_column(
        String(32), default="PENDING", nullable=False, index=True, comment="审批状态"
    )
    current_node: Mapped[str] = mapped_column(
        String(32), default="NONE", nullable=False, comment="当前审批节点"
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    def __repr__(self):
        return f"<LeaveRequest(id={self.id}, user_id={self.user_id}, status='{self.status}')>"


class ExpenseRequest(Base):
    """
    报销单表
    expense_type: 差旅费/办公用品/招待费/交通费/其他
    """
    __tablename__ = "expense_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="申请人ID"
    )
    dept_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="申请人部门ID（提交时快照）"
    )
    expense_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="报销类型"
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False, comment="报销金额（元）")
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, comment="费用发生日期")
    reason: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="报销事由"
    )
    attachments: Mapped[list] = mapped_column(
        JSON, default=list, nullable=True, comment="凭证附件路径列表"
    )
    status: Mapped[str] = mapped_column(
        String(32), default="PENDING", nullable=False, index=True, comment="审批状态"
    )
    current_node: Mapped[str] = mapped_column(
        String(32), default="NONE", nullable=False, comment="当前审批节点"
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    def __repr__(self):
        return f"<ExpenseRequest(id={self.id}, user_id={self.user_id}, status='{self.status}')>"


class ApprovalRecord(Base):
    """
    审批流水表（请假与报销共用）
    biz_type: LEAVE/EXPENSE；node_name: MANAGER/BOSS
    """
    __tablename__ = "approval_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    biz_type: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True, comment="业务类型 LEAVE/EXPENSE"
    )
    biz_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="业务单据ID"
    )
    node_name: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="审批节点 MANAGER/BOSS"
    )
    approver_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="审批人ID"
    )
    approver_role: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="审批人角色编码"
    )
    action_type: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="审批动作 APPROVE/REJECT"
    )
    comment_text: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, comment="审批意见"
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, comment="审批时间"
    )

    def __repr__(self):
        return f"<ApprovalRecord(biz={self.biz_type}#{self.biz_id}, node='{self.node_name}', action='{self.action_type}')>"
