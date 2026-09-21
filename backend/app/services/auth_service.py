# ============================================================
# 认证服务层
# 用户注册、登录、密码修改
# ============================================================

from typing import Optional, Tuple
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.core.exceptions import (
    DuplicateException,
    AuthenticationException,
    AccountLockedException,
    NotFoundException,
)
from app.models.user import User, Role
from app.schemas.auth import RegisterRequest, UserInfo
from app.services.audit_service import add_audit_log, get_client_info


class AuthService:
    """认证业务逻辑"""

    # 时间比较辅助：SQLite 读取的 datetime 为 naive（无时区），统一按 naive UTC 比较
    @staticmethod
    def _now_naive():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _remaining_minutes(locked_until) -> int:
        if not locked_until:
            return 0
        now = AuthService._now_naive()
        try:
            delta = locked_until - now
        except Exception:
            return 0
        return max(1, int(delta.total_seconds() // 60) + 1)

    @staticmethod
    def _is_locked(user) -> bool:
        if not user.locked_until:
            return False
        return AuthService._now_naive() < user.locked_until

    @staticmethod
    def register(db: Session, request: RegisterRequest) -> User:
        """用户注册"""
        # 检查用户名唯一性
        if db.query(User).filter(User.username == request.username).first():
            raise DuplicateException("用户名已被占用")

        # 检查邮箱唯一性
        if request.email and db.query(User).filter(User.email == request.email).first():
            raise DuplicateException("邮箱已被注册")

        # 默认角色：employee
        employee_role = db.query(Role).filter(Role.code == "employee").first()

        user = User(
            username=request.username,
            password_hash=hash_password(request.password),
            email=request.email,
            real_name=request.real_name,
            dept_id=request.dept_id,
            role_id=employee_role.id if employee_role else 1,
        )
        db.add(user)
        db.flush()
        db.refresh(user)
        return user

    @staticmethod
    def login(
        db: Session, username: str, password: str,
        ip: Optional[str] = None, user_agent: Optional[str] = None,
    ) -> Tuple[str, User]:
        """
        用户登录（含失败计数、账号锁定、审计留痕）

        返回: (access_token, User)

        异常:
            AuthenticationException: 用户名或密码错误
            AccountLockedException: 账号已被暂时锁定
        """
        user = db.query(User).filter(User.username == username).first()

        # 统一错误信息，避免泄露用户是否存在
        if not user:
            add_audit_log(
                db=db, module="login", action="login_failed", status="failure",
                username=username, ip=ip, user_agent=user_agent,
            )
            db.commit()  # 失败审计必须落库，接口层异常回滚不能吞掉
            raise AuthenticationException("用户名或密码错误")

        # 账号被管理员禁用
        if user.status == 0:
            add_audit_log(
                db=db, module="login", action="login_blocked", status="blocked",
                user_id=user.id, username=user.username,
                ip=ip, user_agent=user_agent,
            )
            db.commit()
            raise AuthenticationException("账号已被禁用，请联系管理员")

        # 账号锁定判断（锁定到期则自动解锁）
        if AuthService._is_locked(user):
            mins = AuthService._remaining_minutes(user.locked_until)
            add_audit_log(
                db=db, module="login", action="login_blocked", status="blocked",
                user_id=user.id, username=user.username,
                detail={"reason": "locked"}, ip=ip, user_agent=user_agent,
            )
            db.commit()
            raise AccountLockedException(f"账号因连续登录失败已被锁定，请在 {mins} 分钟后重试")

        # 密码校验
        if not verify_password(password, user.password_hash):
            user.failed_attempts = (user.failed_attempts or 0) + 1
            if user.failed_attempts >= settings.LOGIN_MAX_FAILURES:
                # 达到阈值，锁定账号
                user.locked_until = AuthService._now_naive() + timedelta(
                    minutes=settings.LOGIN_LOCK_MINUTES
                )
                user.failed_attempts = 0
                add_audit_log(
                    db=db, module="login", action="login_locked", status="blocked",
                    user_id=user.id, username=user.username,
                    detail={"message": "连续失败达到阈值"},
                    ip=ip, user_agent=user_agent,
                )
            else:
                add_audit_log(
                    db=db, module="login", action="login_failed", status="failure",
                    user_id=user.id, username=user.username,
                    detail={"failed_attempts": user.failed_attempts},
                    ip=ip, user_agent=user_agent,
                )
            # 必须 commit：失败计数与锁定状态要跨请求生效，
            # 否则接口层 get_db 的异常回滚会把计数一起丢弃
            db.commit()
            raise AuthenticationException("用户名或密码错误")

        # 登录成功：清除失败计数与锁定
        user.failed_attempts = 0
        user.locked_until = None
        role = db.query(Role).filter(Role.id == user.role_id).first()

        # 生成 JWT（附带角色编码，避免后续再查库）
        extra_claims = {
            "username": user.username,
            "role": role.code if role else "employee",
            "role_name": role.name if role else "普通员工",
        }
        token = create_access_token(
            subject=str(user.id),
            extra_claims=extra_claims,
        )

        add_audit_log(
            db=db, module="login", action="login_success", status="success",
            user_id=user.id, username=user.username,
            target_type="user", target_id=str(user.id),
            ip=ip, user_agent=user_agent,
        )

        return token, user

    @staticmethod
    def change_password(
        db: Session, user_id: int, old_password: str, new_password: str
    ) -> None:
        """
        修改密码
        使用 user_id 重新查询用户，确保操作在正确的 session 中执行
        （因为 get_current_user 返回的是 detached 对象，不能直接修改）
        """
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise NotFoundException("用户不存在")

        if not verify_password(old_password, user.password_hash):
            raise AuthenticationException("旧密码错误")

        user.password_hash = hash_password(new_password)
        db.flush()

    @staticmethod
    def get_user_info(user: User) -> dict:
        """
        获取用户完整信息（含角色名）
        user.role 已通过 joinedload 预加载到内存，无需数据库查询
        """
        role_name = user.role.name if user.role else "普通员工"
        return {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "position": user.position,
            "department": user.dept.name if user.dept else None,
            "dept_id": user.dept_id,
            "gender": user.gender,
            "entry_date": user.entry_date,
            "role_id": user.role_id,
            "role_name": role_name,
            "permissions": user.role.permissions if user.role else [],
            "status": user.status,
            "created_at": user.created_at,
        }
