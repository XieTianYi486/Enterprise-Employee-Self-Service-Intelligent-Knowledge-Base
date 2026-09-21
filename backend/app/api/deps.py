# ============================================================
# FastAPI 依赖注入
# JWT 认证、用户获取、权限校验
# ============================================================

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_token_payload
from app.db.sqlite import get_db, SessionLocal
from app.models.user import User, Role

# --- Bearer Token 认证方案 ---
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> User:
    """
    从 JWT Token 获取当前登录用户
    所有受保护接口的基础依赖

    使用独立的短生命周期 Session 加载用户，加载完成后立即 expunge，
    返回一个 detached 但数据已完全加载的 User 对象。
    这样即使用户请求的主 Session 发生 rollback（会无条件 expire 所有对象），
    也不会影响 current_user，彻底避免 "not bound to a Session" 错误。

    返回:
        当前登录的 User 对象（detached，role 已预加载）

    异常:
        401: Token 缺失或无效
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )

    token = credentials.credentials
    payload = get_token_payload(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期，请重新登录",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 格式无效",
        )

    # --- 使用独立 Session 加载用户 ---
    # 这个 Session 仅用于加载 User 及其 role，加载完成后立即关闭，
    # User 对象通过 expunge 脱离 Session，不受后续主 Session 的任何影响
    user_db = SessionLocal()
    try:
        user = (
            user_db.query(User)
            .options(joinedload(User.role), joinedload(User.dept))
            .filter(User.id == int(user_id))
            .first()
        )

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
            )

        if user.status == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用，请联系管理员",
            )

        # 强制访问 role 属性，确保 joinedload 的数据已加载到内存
        # （正常情况下 joinedload 已保证，此处是额外的安全保障）
        _ = user.role

        # 将 User 从当前 Session 中 expunge（脱离），
        # 使其成为 detached 对象。所有已加载的属性保持在内存中，
        # 访问时不会触发数据库查询
        user_db.expunge(user)

        return user

    finally:
        user_db.close()


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前活跃用户（status=1）"""
    return current_user


def require_role(role_codes: list[str]):
    """
    角色权限校验工厂函数

    current_user 是 detached 对象（已在 get_current_user 中 expunge），
    但 role 已通过 joinedload 预加载到内存，访问 user.role 不会触发数据库查询。

    使用方式:
        @router.get("/admin/users")
        def admin_endpoint(user = Depends(require_role(["super_admin"]))):
            ...
    """

    def checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        # role 已通过 joinedload 预加载，无需数据库查询
        if current_user.role is None or current_user.role.code not in role_codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足，无法执行此操作",
            )
        return current_user

    return checker


# --- 预设的角色检查器 ---
require_super_admin = require_role(["super_admin"])
require_knowledge_admin = require_role(["super_admin", "knowledge_admin"])
require_dept_admin = require_role(["super_admin", "knowledge_admin", "dept_admin"])


def get_security_level(role_code: str) -> int:
    """
    根据用户角色码确定可访问的文档密级上限

    密级定义:
        1 = 公开, 2 = 内部, 3 = 机密, 4 = 绝密

    角色映射:
        super_admin     → 4 (绝密)
        knowledge_admin → 4 (绝密)
        dept_admin      → 3 (机密)
        boss            → 2 (内部)
        employee        → 1 (公开)
    """
    if role_code in ("super_admin", "knowledge_admin"):
        return 4
    if role_code == "dept_admin":
        return 3
    if role_code == "boss":
        return 2
    return 1  # employee 及未知角色默认仅看公开


def has_permission(user: User, permission: str) -> bool:
    """
    校验用户角色权限点列表是否包含指定权限。

    匹配规则：
      - "*"          ：全部权限
      - 精确匹配      ：如 "documents:read"
      - 模块通配      ：如 "documents:*" 覆盖该模块下全部权限点
    """
    if user.role is None:
        return False
    perms = user.role.permissions or []
    module = permission.split(":", 1)[0]
    return (
        "*" in perms
        or permission in perms
        or f"{module}:*" in perms
    )


def require_permission(permission: str):
    """
    权限点校验工厂函数。

    与 require_role 的分工：角色码控制管理功能（admin 接口），
    权限点控制业务功能开关（角色管理页可勾选的那些权限）。

    使用方式:
        @router.get("/documents")
        def list_documents(user=Depends(require_permission("documents:read"))):
            ...
    """

    def checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足，无法执行此操作",
            )
        return current_user

    return checker
