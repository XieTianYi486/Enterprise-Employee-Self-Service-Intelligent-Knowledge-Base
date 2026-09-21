# ============================================================
# 工作台统计接口
# 按角色返回不同的统计看板结构：
#   普通员工   → 个人办公台（余额/在途单据/本人请假分布）
#   部门管理员 → 部门管理台（本部门待办/人数/请假类型分布）
#   总经理     → 终审台（待终审/全局趋势/部门对比）
#   超级管理员 → 全局看板（+ 用户/文档/问答规模指标）
#   知识库管理员→ 知识运营台（文档/审核/问答量）
# ============================================================

from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from sqlalchemy import String
from sqlalchemy.sql import expression as expr

from app.db.sqlite import get_db
from app.api.deps import get_current_active_user
from app.models.user import User, Department
from app.models.document import Document
from app.models.chat import ChatLog
from app.models.announcement import Announcement
from app.models.workflow import LeaveRequest, ExpenseRequest, ApprovalRecord
from app.schemas.common import APIResponse
from app.services.workflow_service import WorkflowService

router = APIRouter(tags=["工作台"])


def _recent_months(n: int = 6) -> list[str]:
    """返回最近 n 个月的 yyyy-MM 列表（含当月，升序）"""
    today = date.today()
    result = []
    year, month = today.year, today.month
    for _ in range(n):
        result.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(result))


def _month_series(db: Session, model, date_col, months: list[str], amount_col=None):
    """
    按月聚合统计：amount_col 为 None 时统计条数（count），
    传入金额列时统计合计（sum）。

    实现说明：SQLite 中 func.strftime 作用于 DateTime 列时会把 UTC 时间
    直接当本地时间格式化，故用 substr(CAST(date_col AS TEXT), 1, 7)
    截取 ISO 时间戳的 yyyy-MM 前缀做月份分组。
    """
    month_expr = func.substr(expr.cast(date_col, String), 1, 7)
    value = func.sum(amount_col) if amount_col is not None else func.count(model.id)
    rows = (
        db.query(month_expr.label("m"), func.coalesce(value, 0))
        .filter(month_expr.in_(months))
        .group_by("m")
        .all()
    )
    mapping = {m: float(v) for m, v in rows}
    return [mapping.get(m, 0) for m in months]


def _type_distribution(db: Session, query):
    """请假类型分布：[{name, value}]"""
    rows = query.with_entities(LeaveRequest.leave_type, func.count(LeaveRequest.id)) \
        .group_by(LeaveRequest.leave_type).all()
    return [{"name": t, "value": c} for t, c in rows]


def _recent_announcements(db: Session, limit: int = 5) -> list[dict]:
    """最近有效公告"""
    now = datetime.utcnow()
    items = (
        db.query(Announcement)
        .filter(
            Announcement.is_published == 1,
            (Announcement.expire_at.is_(None)) | (Announcement.expire_at > now),
        )
        .order_by(Announcement.publish_at.desc())
        .limit(limit)
        .all()
    )
    return [{"id": a.id, "title": a.title, "publish_at": str(a.publish_at)} for a in items]


def _bill_dicts(db: Session, bills) -> list[dict]:
    """批量序列化单据（复用工作流服务的序列化与姓名映射）"""
    if not bills:
        return []
    user_ids = {b.user_id for b in bills}
    name_map = WorkflowService._user_name_map(db, user_ids)
    return [WorkflowService._bill_to_dict(b, name_map.get(b.user_id)) for b in bills]


def _latest_bills(leave_query, expense_query, limit: int = 5) -> list:
    """请假 + 报销混合，按单据 ID（即提交顺序）取最新 limit 条"""
    leaves = leave_query.all()
    expenses = expense_query.all()
    return sorted(leaves + expenses, key=lambda b: b.id, reverse=True)[:limit]


def _employee_stats(db: Session, user: User) -> dict:
    """普通员工：个人办公台"""
    pending_leaves = db.query(LeaveRequest).filter(
        LeaveRequest.user_id == user.id, LeaveRequest.status == "PENDING"
    ).count()
    pending_expenses = db.query(ExpenseRequest).filter(
        ExpenseRequest.user_id == user.id, ExpenseRequest.status == "PENDING"
    ).count()
    month_start = date.today().replace(day=1)
    approved_month = db.query(LeaveRequest).filter(
        LeaveRequest.user_id == user.id,
        LeaveRequest.status == "APPROVED",
        LeaveRequest.start_date >= month_start,
    ).count()

    balance = WorkflowService.get_balance(db, user.id)
    my_leaves = db.query(LeaveRequest).filter(LeaveRequest.user_id == user.id)

    return {
        "cards": [
            {"label": "年假剩余", "value": balance["annual_left"], "unit": "天", "sub": f"总额 {balance['annual_total']} 天"},
            {"label": "调休剩余", "value": balance["compensatory_left"], "unit": "天", "sub": f"总额 {balance['compensatory_total']} 天"},
            {"label": "待审批单据", "value": pending_leaves + pending_expenses, "unit": "张", "sub": f"请假 {pending_leaves} · 报销 {pending_expenses}"},
            {"label": "本月已通过请假", "value": approved_month, "unit": "张", "sub": "审批状态可查"},
        ],
        "type_dist": _type_distribution(db, my_leaves),
        "trend": None,
        "dept_dist": None,
        "announcements": _recent_announcements(db),
        # 最近单据：请假 + 报销混合，按提交时间取最新 5 条
        "recent": _bill_dicts(db, _latest_bills(
            db.query(LeaveRequest).filter(LeaveRequest.user_id == user.id).limit(5),
            db.query(ExpenseRequest).filter(ExpenseRequest.user_id == user.id).limit(5),
        )),
    }


def _dept_admin_stats(db: Session, user: User) -> dict:
    """部门管理员：部门管理台"""
    dept_id = user.dept_id
    dept_users = db.query(User.id).filter(User.dept_id == dept_id, User.status == 1).subquery()
    member_count = db.query(User).filter(User.dept_id == dept_id, User.status == 1).count()

    todo = db.query(LeaveRequest).filter(
        LeaveRequest.status == "PENDING",
        LeaveRequest.current_node == "MANAGER",
        LeaveRequest.dept_id == dept_id,
    ).count()
    todo += db.query(ExpenseRequest).filter(
        ExpenseRequest.status == "PENDING",
        ExpenseRequest.current_node == "MANAGER",
        ExpenseRequest.dept_id == dept_id,
    ).count()

    month_start = date.today().replace(day=1)
    month_leaves = db.query(LeaveRequest).filter(
        LeaveRequest.dept_id == dept_id, LeaveRequest.start_date >= month_start
    ).count()
    month_expense = db.query(func.coalesce(func.sum(ExpenseRequest.amount), 0)).filter(
        ExpenseRequest.dept_id == dept_id,
        ExpenseRequest.status == "APPROVED",
        ExpenseRequest.expense_date >= month_start,
    ).scalar()

    dept_leaves = db.query(LeaveRequest).filter(LeaveRequest.dept_id == dept_id)

    return {
        "cards": [
            {"label": "本部门待办", "value": todo, "unit": "张", "sub": "部门经理节点待审"},
            {"label": "部门人数", "value": member_count, "unit": "人", "sub": "在职员工"},
            {"label": "本月请假单", "value": month_leaves, "unit": "张", "sub": "本部门提交"},
            {"label": "本月报销额", "value": round(float(month_expense or 0), 0), "unit": "元", "sub": "已通过单据"},
        ],
        "type_dist": _type_distribution(db, dept_leaves),
        "trend": None,
        "dept_dist": None,
        "announcements": _recent_announcements(db),
        # 最近单据：请假 + 报销混合，按提交时间取最新 5 条
        "recent": _bill_dicts(db, _latest_bills(
            db.query(LeaveRequest).filter(LeaveRequest.dept_id == dept_id).limit(5),
            db.query(ExpenseRequest).filter(ExpenseRequest.dept_id == dept_id).limit(5),
        )),
    }


def _boss_stats(db: Session, user: User, is_super: bool = False) -> dict:
    """总经理/超级管理员：全局看板"""
    boss_todo = db.query(LeaveRequest).filter(
        LeaveRequest.status == "PENDING", LeaveRequest.current_node == "BOSS"
    ).count()
    boss_todo += db.query(ExpenseRequest).filter(
        ExpenseRequest.status == "PENDING", ExpenseRequest.current_node == "BOSS"
    ).count()

    month_start = date.today().replace(day=1)
    month_leaves = db.query(LeaveRequest).filter(LeaveRequest.start_date >= month_start).count()
    month_expense = db.query(func.coalesce(func.sum(ExpenseRequest.amount), 0)).filter(
        ExpenseRequest.status == "APPROVED",
        ExpenseRequest.expense_date >= month_start,
    ).scalar()
    employee_count = db.query(User).filter(User.status == 1).count()

    months = _recent_months(6)
    leave_trend = _month_series(db, LeaveRequest, LeaveRequest.start_date, months)
    expense_trend = _month_series(db, ExpenseRequest, ExpenseRequest.expense_date, months, ExpenseRequest.amount)

    dept_dist = (
        db.query(Department.name, func.count(LeaveRequest.id))
        .outerjoin(LeaveRequest, LeaveRequest.dept_id == Department.id)
        .group_by(Department.name)
        .all()
    )
    dept_dist = [{"name": n, "value": c} for n, c in dept_dist if n]

    cards = [
        {"label": "待终审单据", "value": boss_todo, "unit": "张", "sub": "总经理节点"},
        {"label": "本月请假单", "value": month_leaves, "unit": "张", "sub": "全公司"},
        {"label": "本月报销额", "value": round(float(month_expense or 0), 0), "unit": "元", "sub": "已通过单据"},
        {"label": "在职员工", "value": employee_count, "unit": "人", "sub": "全公司"},
    ]

    if is_super:
        doc_count = db.query(Document).count()
        qa_count = db.query(ChatLog).count()
        cards.append({"label": "知识文档", "value": doc_count, "unit": "份", "sub": "知识库存量"})
        cards.append({"label": "累计问答", "value": qa_count, "unit": "次", "sub": "全部问答日志"})

    # 最近单据：请假 + 报销混合，按提交时间取最新 5 条
    recent = _latest_bills(
        db.query(LeaveRequest).limit(5),
        db.query(ExpenseRequest).limit(5),
    )

    return {
        "cards": cards,
        "type_dist": None,
        "trend": {"months": months, "leave": leave_trend, "expense": expense_trend},
        "dept_dist": dept_dist,
        "announcements": _recent_announcements(db),
        "recent": _bill_dicts(db, recent),
    }


def _knowledge_stats(db: Session, user: User) -> dict:
    """知识库管理员：知识运营台"""
    doc_count = db.query(Document).count()
    review_pending = db.query(Document).filter(Document.review_status == 1).count()
    month_start = date.today().replace(day=1)
    qa_month = db.query(ChatLog).filter(ChatLog.created_at >= month_start).count()
    employee_count = db.query(User).filter(User.status == 1).count()

    months = _recent_months(6)
    qa_trend = _month_series(db, ChatLog, ChatLog.created_at, months)

    return {
        "cards": [
            {"label": "知识文档", "value": doc_count, "unit": "份", "sub": "知识库存量"},
            {"label": "待审核文档", "value": review_pending, "unit": "份", "sub": "知识审核队列"},
            {"label": "本月问答", "value": qa_month, "unit": "次", "sub": "员工问答量"},
            {"label": "在职员工", "value": employee_count, "unit": "人", "sub": "全公司"},
        ],
        "type_dist": None,
        "trend": {"months": months, "leave": qa_trend, "expense": [0] * len(months)},
        "dept_dist": None,
        "announcements": _recent_announcements(db),
        "recent": [],
    }


@router.get("/workbench/stats", response_model=APIResponse, summary="工作台统计")
def get_workbench_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """按当前用户角色返回工作台统计看板"""
    role_code = current_user.role.code if current_user.role else "employee"

    if role_code == "employee":
        data = _employee_stats(db, current_user)
    elif role_code == "dept_admin":
        data = _dept_admin_stats(db, current_user)
    elif role_code == "boss":
        data = _boss_stats(db, current_user, is_super=False)
    elif role_code == "super_admin":
        data = _boss_stats(db, current_user, is_super=True)
    else:  # knowledge_admin
        data = _knowledge_stats(db, current_user)

    data["role"] = role_code
    data["user_name"] = current_user.real_name or current_user.username
    data["role_name"] = current_user.role.name if current_user.role else "普通员工"
    return APIResponse(code=0, message="success", data=data)
