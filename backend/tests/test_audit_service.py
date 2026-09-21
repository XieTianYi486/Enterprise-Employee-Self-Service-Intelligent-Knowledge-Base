# ============================================================
# 审计日志服务单元测试
# 覆盖：审计写入落库、登录失败审计 + 防爆破计数不被回滚
# ============================================================

import pytest

from app.core.exceptions import AuthenticationException
from app.models.audit import AuditLog
from app.services.audit_service import add_audit_log
from app.services.auth_service import AuthService


class TestAddAuditLog:
    """审计日志写入"""

    def test_add_audit_log_writes_record(self, db):
        """回归：add_audit_log 必须真实写入 audit_logs 表"""
        add_audit_log(
            db=db, module="security", action="test_action", status="success",
            user_id=1, username="tester", target_type="user", target_id="1",
            detail={"k": "v"}, ip="127.0.0.1", user_agent="pytest",
        )
        db.commit()

        log = db.query(AuditLog).filter(AuditLog.action == "test_action").first()
        assert log is not None
        assert log.module == "security"
        assert log.status == "success"
        assert log.username == "tester"
        assert log.ip == "127.0.0.1"

    def test_login_failure_writes_audit_and_keeps_fail_count(self, db, employee_user):
        """回归：登录失败时审计记录落库，且防爆破计数不被回滚"""
        with pytest.raises(AuthenticationException):
            AuthService.login(db, employee_user.username, "wrongpass")
        db.commit()

        # 失败计数已提交（跨请求生效）
        assert employee_user.failed_attempts == 1
        # 失败审计已落库
        log = db.query(AuditLog).filter(
            AuditLog.action == "login_failed",
            AuditLog.username == employee_user.username,
        ).first()
        assert log is not None
        assert log.status == "failure"

    def test_login_success_writes_audit(self, db, employee_user):
        """登录成功同样写入审计"""
        AuthService.login(db, employee_user.username, "test123456")
        db.commit()

        log = db.query(AuditLog).filter(
            AuditLog.action == "login_success",
            AuditLog.username == employee_user.username,
        ).first()
        assert log is not None
        assert log.status == "success"

    def test_审计写入失败不回滚调用方未提交改动(self, db, employee_user):
        """回归：审计落库自身失败（flush 抛错）时，调用方待提交改动必须保留

        add_audit_log 依赖 SAVEPOINT 隔离：审计 INSERT 失败只回滚审计本身，
        不能把调用方的未提交改动（如防爆破计数）一起丢掉。
        """
        from app.models.user import User

        employee_user.failed_attempts = 3

        # detail 含不可 JSON 序列化对象 -> AuditLog flush 时抛 TypeError
        add_audit_log(
            db=db, module="security", action="audit_flush_failure",
            detail={"bad": object()},
        )  # 异常被审计服务吞掉，不得向外抛出

        # 调用方的改动未被回滚
        assert employee_user.failed_attempts == 3

        db.commit()
        db.expire_all()
        # 失败的那条审计没有落库
        assert db.query(AuditLog).filter(
            AuditLog.action == "audit_flush_failure"
        ).count() == 0
        # 调用方改动已成功提交
        assert db.query(User).filter(User.id == employee_user.id).first().failed_attempts == 3
