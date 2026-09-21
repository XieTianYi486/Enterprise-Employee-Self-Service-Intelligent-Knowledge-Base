# ============================================================
# 工单接口
# 员工端：提交工单、查看我的工单
# 管理端：查看全部工单、处理工单（回复 + 状态流转）
# ============================================================

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.db.sqlite import get_db
from app.api.deps import (
    get_current_active_user,
    require_knowledge_admin,
)
from app.models.user import User
from app.models.ticket import Ticket
from app.schemas.common import APIResponse, PaginatedData
from app.schemas.ticket import (
    TicketCreateRequest, TicketReplyRequest, TicketStatusRequest, TicketInfo,
)
from app.services.notification_service import notify_user

# 员工端路由
router = APIRouter(prefix="/tickets", tags=["工单"])

# 管理端路由
admin_router = APIRouter(prefix="/admin/tickets", tags=["工单管理"])

# 允许的状态与优先级
VALID_STATUS = {"pending", "processing", "resolved", "closed"}
VALID_PRIORITY = {"high", "medium", "low"}

STATUS_LABEL = {
    "pending": "待处理",
    "processing": "处理中",
    "resolved": "已解决",
    "closed": "已关闭",
}


def _serialize(t: Ticket, db: Session) -> dict:
    """序列化工单，补充提交人与处理人姓名"""
    creator = db.query(User).filter(User.id == t.created_by).first()
    handler = db.query(User).filter(User.id == t.handler_id).first() if t.handler_id else None
    return TicketInfo(
        id=t.id, title=t.title, question=t.question, detail=t.detail,
        status=t.status, priority=t.priority, reply=t.reply, reply_count=t.reply_count,
        session_id=t.session_id, created_by=t.created_by, handler_id=t.handler_id,
        created_at=t.created_at, updated_at=t.updated_at, resolved_at=t.resolved_at,
        creator_name=creator.real_name or creator.username if creator else None,
        handler_name=handler.real_name or handler.username if handler else None,
    ).model_dump()


# ==================== 员工端 ====================

@router.post("", response_model=APIResponse, summary="提交工单")
def create_ticket(
    data: TicketCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """员工提交人工兜底工单"""
    priority = data.priority if data.priority in VALID_PRIORITY else "medium"
    ticket = Ticket(
        title=data.title,
        question=data.question,
        detail=data.detail,
        session_id=data.session_id,
        priority=priority,
        created_by=current_user.id,
        status="pending",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return APIResponse(code=0, message="工单已提交，等待人工处理", data=_serialize(ticket, db))


@router.get("", response_model=APIResponse, summary="我的工单")
def list_my_tickets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查看当前用户提交的工单列表"""
    query = db.query(Ticket).filter(Ticket.created_by == current_user.id)
    if status in VALID_STATUS:
        query = query.filter(Ticket.status == status)
    query = query.order_by(Ticket.id.desc())

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    data = [_serialize(t, db) for t in items]
    return APIResponse(
        code=0, message="success",
        data=PaginatedData.from_query(data, total, page, page_size).model_dump(),
    )


@router.get("/{ticket_id}", response_model=APIResponse, summary="工单详情")
def get_my_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查看单个工单（仅本人或管理员）"""
    # 管理员可查看任意工单
    is_admin = current_user.role is not None and current_user.role.code in (
        "super_admin", "knowledge_admin", "dept_admin"
    )
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return APIResponse(code=1, message="工单不存在")
    if ticket.created_by != current_user.id and not is_admin:
        return APIResponse(code=403, message="无权限查看该工单")
    return APIResponse(code=0, message="success", data=_serialize(ticket, db))


# ==================== 管理端 ====================

@admin_router.get("", response_model=APIResponse, summary="工单列表")
def list_all_tickets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """管理员查看全部工单，支持按状态/优先级/关键词筛选"""
    query = db.query(Ticket)
    if status in VALID_STATUS:
        query = query.filter(Ticket.status == status)
    if priority in VALID_PRIORITY:
        query = query.filter(Ticket.priority == priority)
    if keyword:
        query = query.filter(
            (Ticket.title.contains(keyword)) |
            (Ticket.question.contains(keyword))
        )
    query = query.order_by(Ticket.status.asc(), Ticket.id.desc())

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    data = [_serialize(t, db) for t in items]
    return APIResponse(
        code=0, message="success",
        data=PaginatedData.from_query(data, total, page, page_size).model_dump(),
    )


@admin_router.get("/stats", response_model=APIResponse, summary="工单统计")
def ticket_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """工单状态统计（用于管理页标签页角标）"""
    from sqlalchemy import func
    rows = db.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
    counts = {s: 0 for s in VALID_STATUS}
    for s, c in rows:
        counts[s] = c
    counts["total"] = sum(counts.values())
    return APIResponse(code=0, message="success", data=counts)


@admin_router.put("/{ticket_id}/handle", response_model=APIResponse, summary="处理工单")
def handle_ticket(
    ticket_id: int,
    data: TicketReplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """管理员回复并处理工单"""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return APIResponse(code=1, message="工单不存在")

    ticket.reply = data.reply
    ticket.handler_id = current_user.id
    ticket.status = "resolved"
    ticket.resolved_at = datetime.now(timezone.utc)
    ticket.reply_count += 1
    # 站内消息：通知工单提交人
    notify_user(
        db=db, user_id=ticket.created_by, type="TICKET",
        title="您的工单已有回复",
        content=f"工单「{ticket.title}」已处理：{data.reply[:120]}",
        biz_type="TICKET", biz_id=ticket.id,
    )
    db.commit()
    db.refresh(ticket)
    return APIResponse(code=0, message="工单已处理", data=_serialize(ticket, db))


@admin_router.put("/{ticket_id}/status", response_model=APIResponse, summary="更新工单状态")
def update_ticket_status(
    ticket_id: int,
    data: TicketStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """仅更新工单状态（如回退为待处理、关闭等）"""
    if data.status not in VALID_STATUS:
        return APIResponse(code=1, message="非法的工单状态")
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        return APIResponse(code=1, message="工单不存在")

    ticket.status = data.status
    if data.status == "resolved":
        ticket.resolved_at = datetime.now()
    elif data.status == "pending" or data.status == "processing":
        ticket.resolved_at = None
    db.commit()
    db.refresh(ticket)
    return APIResponse(code=0, message="状态已更新", data=_serialize(ticket, db))