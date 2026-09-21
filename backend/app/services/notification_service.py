# ============================================================
# 站内消息服务
# 审批结果 / 工单回复等业务动作的接收人通知
# ============================================================

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.notification import Notification

logger = logging.getLogger(__name__)


def notify_user(
    db: Session,
    user_id: int,
    type: str,
    title: str,
    content: Optional[str] = None,
    biz_type: Optional[str] = None,
    biz_id: Optional[int] = None,
) -> None:
    """
    给指定用户写入一条站内消息。

    使用 SAVEPOINT（嵌套事务）：消息写入失败只回滚消息本身，
    绝不回滚调用方的业务改动（与审计日志同一隔离策略）。
    """
    try:
        with db.begin_nested():
            db.add(Notification(
                user_id=user_id,
                type=type,
                title=title,
                content=content,
                biz_type=biz_type,
                biz_id=biz_id,
            ))
            db.flush()
    except Exception as e:
        logger.warning(f"写入站内消息失败: {e}")
