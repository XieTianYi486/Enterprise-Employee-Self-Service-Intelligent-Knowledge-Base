# ============================================================
# 认证服务单元测试：注册、登录、失败锁定、修改密码
# ============================================================

import pytest

from app.core.exceptions import (
    AuthenticationException,
    AccountLockedException,
    DuplicateException,
    NotFoundException,
)
from app.schemas.auth import RegisterRequest
from app.services.auth_service import AuthService


class TestRegister:
    """用户注册"""

    def test_register_success(self, db, roles):
        request = RegisterRequest(username="new_employee", password="abc123456")
        user = AuthService.register(db, request)
        db.commit()
        assert user.id is not None
        assert user.role_id == roles["employee"].id

    def test_register_duplicate_username(self, db, roles):
        AuthService.register(db, RegisterRequest(
            username="dup_user", password="abc123456"))
        db.commit()
        with pytest.raises(DuplicateException):
            AuthService.register(db, RegisterRequest(
                username="dup_user", password="xyz123456"))

    def test_register_duplicate_email(self, db, roles):
        AuthService.register(db, RegisterRequest(
            username="u_email_1", email="same@x.com", password="abc123456"))
        db.commit()
        with pytest.raises(DuplicateException):
            AuthService.register(db, RegisterRequest(
                username="u_email_2", email="same@x.com", password="abc123456"))


class TestLogin:
    """登录与安全策略"""

    def test_login_success(self, db, employee_user):
        token, user = AuthService.login(db, employee_user.username, "test123456")
        assert token
        assert user.failed_attempts == 0
        assert user.locked_until is None

    def test_login_wrong_password_counts_failure(self, db, employee_user):
        with pytest.raises(AuthenticationException):
            AuthService.login(db, employee_user.username, "wrongpass")
        assert employee_user.failed_attempts == 1

    def test_login_unknown_user(self, db):
        """不存在的用户返回统一错误，不泄露用户是否存在"""
        with pytest.raises(AuthenticationException):
            AuthService.login(db, "ghost_user", "whatever")

    def test_login_locks_after_max_failures(self, db, employee_user):
        """连续失败达到 LOGIN_MAX_FAILURES(5) 次后锁定，正确密码也无法登录"""
        for _ in range(5):
            with pytest.raises(AuthenticationException):
                AuthService.login(db, employee_user.username, "wrongpass")
        with pytest.raises(AccountLockedException):
            AuthService.login(db, employee_user.username, "test123456")

    def test_login_lock_persists_across_requests(self, db, employee_user):
        """回归：每次失败后提交（模拟接口层独立请求），失败计数与锁定跨请求生效"""
        for _ in range(5):
            with pytest.raises(AuthenticationException):
                AuthService.login(db, employee_user.username, "wrongpass")
            db.commit()
        with pytest.raises(AccountLockedException):
            AuthService.login(db, employee_user.username, "test123456")

    def test_disabled_user_cannot_login(self, db, roles):
        from app.core.security import hash_password
        from app.models.user import User

        user = User(
            username="disabled_u",
            password_hash=hash_password("abc123456"),
            role_id=roles["employee"].id,
            status=0,
        )
        db.add(user)
        db.commit()
        with pytest.raises(AuthenticationException):
            AuthService.login(db, "disabled_u", "abc123456")


class TestChangePassword:
    """修改密码"""

    def test_change_password_success(self, db, employee_user):
        AuthService.change_password(db, employee_user.id, "test123456", "newpass666")
        db.commit()
        # 旧密码失效，新密码可登录
        with pytest.raises(AuthenticationException):
            AuthService.login(db, employee_user.username, "test123456")
        token, _ = AuthService.login(db, employee_user.username, "newpass666")
        assert token

    def test_change_password_wrong_old(self, db, employee_user):
        with pytest.raises(AuthenticationException):
            AuthService.change_password(db, employee_user.id, "wrongold", "newpass666")

    def test_change_password_user_not_found(self, db):
        with pytest.raises(NotFoundException):
            AuthService.change_password(db, 999999, "a", "b")
