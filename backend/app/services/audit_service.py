# ============================================================
# 审计日志服务
# 统一的审计留痕入口，供登录/敏感词/文档审核等模块调用
# ============================================================

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


def add_audit_log(
    db: Session,
    module: str,
    action: str,
    status: str = "success",
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[dict] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    写入一条审计日志。

    参数:
        db: 数据库会话
        module: 模块（login/security/sensitive/document/chat/admin）
        action: 动作（login_success / sensitive_hit / document_review ...）
        status: success / failure / blocked
        user_id / username: 操作者
        target_type / target_id / detail: 操作对象与附加信息
        ip / user_agent: 客户端信息
    """
    try:
        log = AuditLog(
            module=module,
            action=action,
            status=status,
            user_id=user_id,
            username=username,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip=ip,
            user_agent=user_agent,
        )
        # 使用 SAVEPOINT（嵌套事务）写入审计日志：
        # 写入失败只回滚审计日志本身，绝不回滚调用方的未提交改动
        # （例如登录接口的失败计数/锁定状态，否则防爆破计数会被连带丢失）
        with db.begin_nested():
            db.add(log)
            db.flush()
    except Exception as e:  # 审计日志写入失败不影响主业务流程
        logger.warning(f"写入审计日志失败: {e}")


def get_client_info(request) -> tuple[Optional[str], Optional[str]]:
    """从 FastAPI Request 提取客户端 IP 与 User-Agent"""
    try:
        ua = request.headers.get("user-agent")
    except Exception:
        ua = None
    try:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else None
    except Exception:
        ip = None
    return ip, ua