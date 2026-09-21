# ============================================================
# 站内消息接口
# 列表（分页）/ 未读数 / 标记已读
# ============================================================

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.sqlite import get_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.common import APIResponse

router = APIRouter(tags=["消息中心"])


@router.get("/notifications", response_model=APIResponse, summary="我的消息列表")
def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    unread_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """我的站内消息（分页）+ 未读总数"""
    q = db.query(Notification).filter(Notification.user_id == current_user.id)
    unread = q.filter(Notification.is_read == False).count()  # noqa: E712
    if unread_only:
        q = q.filter(Notification.is_read == False)  # noqa: E712
    total = q.count()
    items = q.order_by(Notification.id.desc()) \
        .offset((page - 1) * page_size).limit(page_size).all()

    return APIResponse(code=0, message="success", data={
        "total": total,
        "unread": unread,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "content": n.content,
                "biz_type": n.biz_type,
                "biz_id": n.biz_id,
                "is_read": n.is_read,
                "create_time": str(n.create_time),
            }
            for n in items
        ],
    })


@router.post("/notifications/{nid}/read", response_model=APIResponse, summary="标记已读")
def mark_read(
    nid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """将指定消息标记为已读（仅本人消息）"""
    n = db.query(Notification).filter(
        Notification.id == nid, Notification.user_id == current_user.id
    ).first()
    if n is None:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("消息不存在")
    n.is_read = True
    db.flush()
    return APIResponse(code=0, message="已标记为已读")


@router.post("/notifications/read-all", response_model=APIResponse, summary="全部已读")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """将本人全部消息标记为已读"""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,  # noqa: E712
    ).update({"is_read": True})
    db.flush()
    return APIResponse(code=0, message="全部消息已标记为已读")
