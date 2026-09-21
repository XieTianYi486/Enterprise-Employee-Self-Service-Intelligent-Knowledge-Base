# ============================================================
# 安全合规接口
# 敏感词管理（CRUD）+ 审计日志查询
# ============================================================

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.sqlite import get_db
from app.api.deps import require_super_admin, get_current_active_user
from app.models.user import User
from app.models.audit import SensitiveWord, AuditLog
from app.schemas.common import APIResponse, PaginatedData
from app.schemas.security import SensitiveWordCreate, SensitiveWordUpdate
from app.services.sensitive_service import SensitiveService

router = APIRouter(tags=["安全合规"])


# ==================== 敏感词管理 ====================

@router.get("/admin/sensitive-words", response_model=APIResponse, summary="敏感词列表")
def list_sensitive_words(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: Optional[str] = None,
    enabled: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """敏感词列表（分页 + 筛选）"""
    items, total = SensitiveService.list_words(
        db, keyword=keyword, enabled=enabled, page=page, page_size=page_size
    )
    data = [
        {
            "id": w.id, "word": w.word, "category": w.category,
            "level": w.level, "action": w.action,
            "replacement": w.replacement, "enabled": w.enabled,
            "created_at": w.created_at,
        }
        for w in items
    ]
    return APIResponse(
        code=0, message="success",
        data=PaginatedData.from_query(data, total, page, page_size).model_dump()
    )


@router.post("/admin/sensitive-words", response_model=APIResponse, summary="新增敏感词")
def create_sensitive_word(
    data: SensitiveWordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """新增敏感词"""
    word = data.word.strip()
    if not word:
        return APIResponse(code=1001, message="敏感词不能为空")
    try:
        item = SensitiveService.create_word(
            db=db,
            word=word,
            level=data.level,
            action=data.action,
            replacement=data.replacement,
            category=data.category,
        )
    except ValueError as e:
        return APIResponse(code=3002, message=str(e))
    return APIResponse(code=0, message="添加成功", data={"id": item.id})


@router.put("/admin/sensitive-words/{word_id}", response_model=APIResponse, summary="更新敏感词")
def update_sensitive_word(
    word_id: int,
    data: SensitiveWordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """更新敏感词属性或启停状态"""
    fields = {
        "word": data.word.strip() if data.word else None,
        "level": data.level,
        "action": data.action,
        "replacement": data.replacement,
        "category": data.category,
        "enabled": data.enabled,
    }
    try:
        item = SensitiveService.update_word(db, word_id, **fields)
    except LookupError as e:
        return APIResponse(code=3001, message=str(e))
    return APIResponse(code=0, message="更新成功", data={"id": item.id})


@router.delete("/admin/sensitive-words/{word_id}", response_model=APIResponse, summary="删除敏感词")
def delete_sensitive_word(
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """删除敏感词"""
    try:
        SensitiveService.delete_word(db, word_id)
    except LookupError as e:
        return APIResponse(code=3001, message=str(e))
    return APIResponse(code=0, message="已删除")


# ==================== 审计日志 ====================

@router.get("/admin/audit-logs", response_model=APIResponse, summary="审计日志")
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    module: Optional[str] = None,
    action: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """审计日志列表（分页 + 筛选）"""
    query = db.query(AuditLog)
    if module:
        query = query.filter(AuditLog.module == module)
    if action:
        query = query.filter(AuditLog.action == action)
    if keyword:
        query = query.filter(
            (AuditLog.username.contains(keyword)) |
            (AuditLog.detail.like(f"%{keyword}%"))
        )

    total = query.count()
    items = query.order_by(AuditLog.id.desc()) \
        .offset((page - 1) * page_size).limit(page_size).all()
    data = [
        {
            "id": log.id, "module": log.module, "action": log.action,
            "status": log.status, "username": log.username,
            "target_type": log.target_type, "target_id": log.target_id,
            "detail": log.detail, "ip": log.ip, "user_agent": log.user_agent,
            "created_at": log.created_at,
        }
        for log in items
    ]
    return APIResponse(
        code=0, message="success",
        data=PaginatedData.from_query(data, total, page, page_size).model_dump()
    )