# ============================================================
# 权限点校验测试：has_permission / require_permission
# 角色管理页配置的权限点（documents:read 等）必须被接口层强制校验，
# 支持 "*" 全部权限与 "模块:*" 模块通配
# ============================================================

import pytest
from fastapi import HTTPException

from app.api.deps import has_permission, require_permission
from app.models.user import User, Role


def _make_user(perms, with_role=True):
    """构造带指定权限列表的用户（role 关系手动挂载，不依赖数据库）"""
    user = User(username="perm_tester", password_hash="x", role_id=1)
    if with_role:
        user.role = Role(name="测试角色", code="test_role", permissions=perms)
    return user


class TestHasPermission:
    def test_exact_match(self):
        user = _make_user(["documents:read", "chat:ask"])
        assert has_permission(user, "documents:read") is True
        assert has_permission(user, "chat:ask") is True
        assert has_permission(user, "documents:delete") is False
        assert has_permission(user, "stats:read") is False

    def test_star_grants_all(self):
        user = _make_user(["*"])
        assert has_permission(user, "documents:read") is True
        assert has_permission(user, "chat:ask") is True

    def test_module_wildcard(self):
        user = _make_user(["documents:*"])
        assert has_permission(user, "documents:read") is True
        assert has_permission(user, "documents:delete") is True
        assert has_permission(user, "chat:ask") is False

    def test_empty_or_none_denies(self):
        assert has_permission(_make_user([]), "documents:read") is False
        assert has_permission(_make_user(None), "documents:read") is False

    def test_no_role_denies(self):
        user = _make_user(["*"], with_role=False)
        assert has_permission(user, "documents:read") is False


class TestRequirePermission:
    def test_checker_allows_when_permitted(self):
        checker = require_permission("documents:read")
        user = _make_user(["documents:read"])
        assert checker(user) is user

    def test_checker_raises_403_when_denied(self):
        checker = require_permission("documents:read")
        user = _make_user(["chat:ask"])
        with pytest.raises(HTTPException) as exc_info:
            checker(user)
        assert exc_info.value.status_code == 403
