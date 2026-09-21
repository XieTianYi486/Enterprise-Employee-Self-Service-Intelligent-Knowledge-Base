# ============================================================
# 启动安全配置守卫测试（JWT 密钥）
# 回归：
#   1. config.py 的 JWT_SECRET_KEY 不提供可用默认值
#   2. main.py 的 _check_security_config 在 lifespan 启动阶段拒绝
#      空密钥 / 公开占位密钥，且必须早于任何数据库初始化动作
# 背景：.env.example 中的占位密钥公开可见，部署者若未修改直接复制使用，
#       攻击者可用该密钥离线伪造超管 JWT（默认管理员 ID=1 可猜）。
# ============================================================

import asyncio
import re
import secrets
from pathlib import Path

import pytest

import app.main as main_mod
from app.core.config import Settings, settings
from app.main import _check_security_config, app, lifespan

BACKEND_DIR = Path(__file__).resolve().parent.parent

# .env.example 与历史默认值中公开可见的占位密钥，必须全部被拒绝
WEAK_JWT_SECRETS = [
    "jwt-secret-change-in-production",
    "jwt-dev-secret-2024",
    "change-this-to-a-random-secret-key",
]


def _example_jwt_secret() -> str:
    """.env.example 中 JWT_SECRET_KEY 的原始值（缺失时返回空串）"""
    text = (BACKEND_DIR / ".env.example").read_text(encoding="utf-8")
    match = re.search(r"^JWT_SECRET_KEY=(.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


class TestJwtSecretNoUsableDefault:
    """config.py：不允许提供可直接使用的默认密钥"""

    def test_配置类不提供可用默认密钥(self):
        assert Settings.model_fields["JWT_SECRET_KEY"].default == ""

    def test_示例配置的密钥不可直接使用(self):
        """复制 .env.example 即启动的行为必须被禁止：其值要么为空，要么命中黑名单"""
        value = _example_jwt_secret()
        assert value == "" or value in WEAK_JWT_SECRETS


class TestCheckSecurityConfig:
    """main.py：启动守卫的判定逻辑"""

    def test_空密钥拒绝启动(self, monkeypatch):
        monkeypatch.setattr(settings, "JWT_SECRET_KEY", "")
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            _check_security_config()

    @pytest.mark.parametrize("weak", WEAK_JWT_SECRETS)
    def test_公开占位密钥拒绝启动(self, monkeypatch, weak):
        monkeypatch.setattr(settings, "JWT_SECRET_KEY", weak)
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            _check_security_config()

    def test_强随机密钥通过(self, monkeypatch):
        """误杀检查：强随机密钥（与 .env 生成方式一致）不得被拒绝"""
        monkeypatch.setattr(settings, "JWT_SECRET_KEY", secrets.token_urlsafe(48))
        _check_security_config()  # 不抛异常即通过

    def test_当前env配置可通过守卫(self):
        """实际部署配置的密钥必须足够强，否则应用根本起不来"""
        _check_security_config()


class TestLifespanGuardWiring:
    """lifespan：守卫必须真正接线到启动流程"""

    @staticmethod
    def _run_startup():
        async def _startup():
            async with lifespan(app):
                pass

        asyncio.run(_startup())

    def test_弱密钥启动被拒且未执行数据库初始化(self, monkeypatch):
        monkeypatch.setattr(settings, "JWT_SECRET_KEY", "jwt-dev-secret-2024")
        touched = []
        monkeypatch.setattr(main_mod, "init_db", lambda: touched.append("init_db"))
        monkeypatch.setattr(
            main_mod, "_init_default_data", lambda: touched.append("init_data")
        )

        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            self._run_startup()

        assert touched == []  # 必须在任何初始化动作之前拒绝启动

    def test_强密钥可正常完成启动(self, monkeypatch):
        monkeypatch.setattr(settings, "JWT_SECRET_KEY", secrets.token_urlsafe(48))
        order = []
        monkeypatch.setattr(main_mod, "init_db", lambda: order.append("init_db"))
        monkeypatch.setattr(
            main_mod, "_init_default_data", lambda: order.append("init_data")
        )

        async def _startup():
            async with lifespan(app):
                order.append("ready")

        asyncio.run(_startup())
        assert order == ["init_db", "init_data", "ready"]
