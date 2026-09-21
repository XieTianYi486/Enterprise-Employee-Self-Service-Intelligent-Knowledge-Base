# ============================================================
# OA 办公流程接口
# 请假 / 报销 / 假期余额 / 审批中心（两级审批）
# ============================================================

import os
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.sqlite import get_db
from app.api.deps import (
    get_current_active_user,
    require_permission,
)
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.models.workflow import ApprovalRecord
from app.schemas.common import APIResponse
from app.schemas.workflow import LeaveSubmitRequest, ExpenseSubmitRequest, ApprovalRequest
from app.services.workflow_service import WorkflowService
from app.services.audit_service import add_audit_log, get_client_info
from app.services.notification_service import notify_user

router = APIRouter(tags=["办公流程"])

# 报销凭证存储目录：backend/uploads/expenses
# 安全约束：放在 /static 公开挂载之外，凭证只能通过下方鉴权下载接口访问
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
EXPENSE_DIR = os.path.join(BASE_DIR, "uploads", "expenses")
os.makedirs(EXPENSE_DIR, exist_ok=True)

# 凭证大小上限：5MB；允许扩展名
EXPENSE_MAX_SIZE = 5 * 1024 * 1024
EXPENSE_ALLOWED_EXTS = ("jpg", "jpeg", "png", "webp", "pdf")
# 文件名安全校验（防路径穿越）
_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


# ==================== 假期余额 ====================

@router.get("/leaves/balance", response_model=APIResponse, summary="我的假期余额")
def get_my_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查询当前用户当年假期余额（年假/事假/病假/调休）"""
    return APIResponse(
        code=0, message="success",
        data=WorkflowService.get_balance(db, current_user.id)
    )


# ==================== 请假 ====================

@router.post("/leaves", response_model=APIResponse, summary="提交请假申请")
def submit_leave(
    payload: LeaveSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leaves:submit")),
):
    """提交请假申请；按申请人角色计算起始审批节点，免审单据直接通过"""
    bill = WorkflowService.submit_leave(db, current_user, payload)
    add_audit_log(
        db=db, module="leave", action="leave_submit", status="success",
        user_id=current_user.id, username=current_user.username,
        target_type="leave", target_id=str(bill.id),
        detail={"leave_type": bill.leave_type, "days": bill.days},
        ip=get_client_info(request)[0], user_agent=get_client_info(request)[1],
    )
    return APIResponse(
        code=0, message="请假申请已提交",
        data={"id": bill.id, "status": bill.status, "current_node": bill.current_node}
    )


@router.get("/leaves", response_model=APIResponse, summary="请假单列表")
def list_leaves(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    status: Optional[str] = Query(default=None, description="PENDING/APPROVED/REJECTED/CANCELLED"),
    pending_only: bool = Query(default=False, description="仅看待办"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leaves:read")),
):
    """分页查询请假单（按角色收缩数据范围）"""
    result = WorkflowService.list_bills(
        db, WorkflowService.BIZ_LEAVE, current_user,
        page=page, page_size=page_size, status=status, pending_only=pending_only,
    )
    return APIResponse(code=0, message="success", data=result)


@router.get("/leaves/{bill_id}", response_model=APIResponse, summary="请假单详情")
def get_leave_detail(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("leaves:read")),
):
    """请假单详情（含审批流水时间线）"""
    return APIResponse(
        code=0, message="success",
        data=WorkflowService.get_bill_detail(db, WorkflowService.BIZ_LEAVE, bill_id, current_user)
    )


@router.post("/leaves/{bill_id}/cancel", response_model=APIResponse, summary="撤销请假")
def cancel_leave(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """撤销本人待审批的请假单"""
    WorkflowService.cancel(db, WorkflowService.BIZ_LEAVE, bill_id, current_user)
    add_audit_log(
        db=db, module="leave", action="leave_cancel", status="success",
        user_id=current_user.id, username=current_user.username,
        target_type="leave", target_id=str(bill_id),
    )
    return APIResponse(code=0, message="请假已撤销")


# ==================== 报销 ====================

@router.post("/expenses/attachments", response_model=APIResponse, summary="上传报销凭证")
def upload_expense_attachment(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """
    上传报销凭证图片（jpg/png/webp/pdf，最大 5MB）。

    安全约束：分块流式写入并累计计数，即使客户端未提供 file.size
    （值可能为 None）也无法绕过 5MB 上限；文件名由服务端生成。
    """
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "jpg"
    if ext not in EXPENSE_ALLOWED_EXTS:
        return APIResponse(code=3002, message="仅支持 jpg/png/webp/pdf 格式")
    if file.size and file.size > EXPENSE_MAX_SIZE:
        return APIResponse(code=3002, message="凭证大小不能超过 5MB")

    filename = f"{current_user.id}_{uuid.uuid4().hex[:12]}.{ext}"
    file_path = os.path.join(EXPENSE_DIR, filename)
    size = 0
    try:
        with open(file_path, "wb") as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > EXPENSE_MAX_SIZE:
                    raise OverflowError
                f.write(chunk)
    except OverflowError:
        os.remove(file_path)
        return APIResponse(code=3002, message="凭证大小不能超过 5MB")

    return APIResponse(
        code=0, message="上传成功",
        data={"path": f"expenses/attachments/{filename}"}
    )


@router.get("/expenses/attachments/{filename}", summary="下载报销凭证")
def download_expense_attachment(
    filename: str,
    current_user: User = Depends(require_permission("expenses:read")),
):
    """
    鉴权下载报销凭证（替代公开 /static 挂载）。
    所有登录且具备报销查看权限的用户可访问；文件名由服务端生成
    （用户ID+随机12位十六进制），不可枚举猜测。
    """
    if not _FILENAME_RE.match(filename):
        raise NotFoundException("凭证不存在")
    file_path = os.path.join(EXPENSE_DIR, filename)
    # 二次防护：解析后必须仍位于 EXPENSE_DIR 内
    if not os.path.realpath(file_path).startswith(os.path.realpath(EXPENSE_DIR)):
        raise NotFoundException("凭证不存在")
    if not os.path.isfile(file_path):
        raise NotFoundException("凭证不存在")
    return FileResponse(file_path)


@router.post("/expenses", response_model=APIResponse, summary="提交报销申请")
def submit_expense(
    payload: ExpenseSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("expenses:submit")),
):
    """提交报销申请；按申请人角色计算起始审批节点"""
    bill = WorkflowService.submit_expense(db, current_user, payload)
    add_audit_log(
        db=db, module="expense", action="expense_submit", status="success",
        user_id=current_user.id, username=current_user.username,
        target_type="expense", target_id=str(bill.id),
        detail={"expense_type": bill.expense_type, "amount": bill.amount},
        ip=get_client_info(request)[0], user_agent=get_client_info(request)[1],
    )
    return APIResponse(
        code=0, message="报销申请已提交",
        data={"id": bill.id, "status": bill.status, "current_node": bill.current_node}
    )


@router.get("/expenses", response_model=APIResponse, summary="报销单列表")
def list_expenses(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    pending_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("expenses:read")),
):
    """分页查询报销单（按角色收缩数据范围）"""
    result = WorkflowService.list_bills(
        db, WorkflowService.BIZ_EXPENSE, current_user,
        page=page, page_size=page_size, status=status, pending_only=pending_only,
    )
    return APIResponse(code=0, message="success", data=result)


@router.get("/expenses/{bill_id}", response_model=APIResponse, summary="报销单详情")
def get_expense_detail(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("expenses:read")),
):
    """报销单详情（含审批流水时间线）"""
    return APIResponse(
        code=0, message="success",
        data=WorkflowService.get_bill_detail(db, WorkflowService.BIZ_EXPENSE, bill_id, current_user)
    )


@router.post("/expenses/{bill_id}/cancel", response_model=APIResponse, summary="撤销报销")
def cancel_expense(
    bill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """撤销本人待审批的报销单"""
    WorkflowService.cancel(db, WorkflowService.BIZ_EXPENSE, bill_id, current_user)
    add_audit_log(
        db=db, module="expense", action="expense_cancel", status="success",
        user_id=current_user.id, username=current_user.username,
        target_type="expense", target_id=str(bill_id),
    )
    return APIResponse(code=0, message="报销已撤销")


# ==================== 审批中心 ====================

@router.get("/approvals/todo", response_model=APIResponse, summary="我的待办")
def get_todo(
    biz_type: Optional[str] = Query(default=None, description="LEAVE/EXPENSE，不传返回全部"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("approvals:read")),
):
    """
    审批待办列表（按角色返回不同节点）：
    - 部门管理员：本部门 MANAGER 节点单据
    - 总经理：BOSS 节点单据
    - 超级管理员：全部待审单据
    """
    leaves = []
    expenses = []
    if biz_type in (None, WorkflowService.BIZ_LEAVE):
        leaves = WorkflowService.list_bills(
            db, WorkflowService.BIZ_LEAVE, current_user,
            page=page, page_size=page_size, pending_only=True,
        )["items"]
    if biz_type in (None, WorkflowService.BIZ_EXPENSE):
        expenses = WorkflowService.list_bills(
            db, WorkflowService.BIZ_EXPENSE, current_user,
            page=page, page_size=page_size, pending_only=True,
        )["items"]
    items = sorted(
        leaves + expenses,
        key=lambda x: x["create_time"],
        reverse=True,
    )
    return APIResponse(code=0, message="success", data={"items": items})


@router.get("/approvals/done", response_model=APIResponse, summary="我的已办")
def get_done(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("approvals:read")),
):
    """我已审批的流水记录"""
    q = db.query(ApprovalRecord).filter(ApprovalRecord.approver_id == current_user.id)
    total = q.count()
    records = q.order_by(ApprovalRecord.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "id": r.id,
            "biz_type": r.biz_type,
            "biz_id": r.biz_id,
            "node_name": r.node_name,
            "action_type": r.action_type,
            "comment_text": r.comment_text,
            "create_time": str(r.create_time),
        }
        for r in records
    ]
    return APIResponse(
        code=0, message="success",
        data={"total": total, "page": page, "page_size": page_size, "items": items}
    )


@router.post("/approvals/{biz_type}/{bill_id}", response_model=APIResponse, summary="审批单据")
def approve_bill(
    biz_type: str,
    bill_id: int,
    payload: ApprovalRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("approvals:approve")),
):
    """
    审批动作（两级审批引擎核心）：
    通过 → 经理节点且超阈值时升级总经理终审，否则结束流程（请假扣减余额）；
    驳回 → 单据关闭。
    """
    if biz_type not in (WorkflowService.BIZ_LEAVE, WorkflowService.BIZ_EXPENSE):
        from app.core.exceptions import ValidationException
        raise ValidationException("业务类型必须是 LEAVE 或 EXPENSE")

    result = WorkflowService.approve(
        db, biz_type, bill_id, payload.action, payload.comment, current_user
    )
    # 站内消息：通知申请人审批结果
    applicant_id = result.get("user_id")
    if applicant_id:
        biz_label = "请假" if biz_type == WorkflowService.BIZ_LEAVE else "报销"
        if result["status"] == "REJECTED":
            title = f"您的{biz_label}申请被驳回"
            content = f"{biz_label}单 #{bill_id} 被驳回" + (f"：{payload.comment}" if payload.comment else "")
        elif result["status"] == "APPROVED":
            title = f"您的{biz_label}申请已通过"
            content = f"{biz_label}单 #{bill_id} 审批通过"
        else:
            title = f"您的{biz_label}申请已转交总经理终审"
            content = f"{biz_label}单 #{bill_id} 已通过部门经理审批，转交总经理终审"
        notify_user(
            db=db, user_id=applicant_id, type="APPROVAL",
            title=title, content=content,
            biz_type=biz_type, biz_id=bill_id,
        )
    add_audit_log(
        db=db, module="approval", action="approval_action", status="success",
        user_id=current_user.id, username=current_user.username,
        target_type=biz_type.lower(), target_id=str(bill_id),
        detail={"action": payload.action, "result": result},
        ip=get_client_info(request)[0], user_agent=get_client_info(request)[1],
    )
    return APIResponse(code=0, message="审批完成", data=result)
