# ============================================================
# 考勤服务单元测试（简化版）
# 覆盖：打卡/签退流程、状态评定规则、重复打卡防护
# ============================================================

import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.core.exceptions import ValidationException
from app.core.security import hash_password
from app.models.user import User
from app.services.attendance_service import AttendanceService


def _make_user(db, roles):
    user = User(
        username=f"att_{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("test123456"),
        role_id=roles["employee"].id,
    )
    db.add(user)
    db.flush()
    return user


class TestEvaluateStatus:
    """状态评定：按打卡/签退时间与规则比较（纯函数，时间可控）"""

    def test_normal_day(self):
        rec = SimpleNamespace(
            clock_in=datetime(2026, 9, 21, 8, 55),
            clock_out=datetime(2026, 9, 21, 18, 5),
        )
        assert AttendanceService._evaluate_status(rec) == "NORMAL"

    def test_late_arrival(self):
        rec = SimpleNamespace(
            clock_in=datetime(2026, 9, 21, 9, 10),
            clock_out=datetime(2026, 9, 21, 18, 30),
        )
        assert AttendanceService._evaluate_status(rec) == "LATE"

    def test_early_leave(self):
        rec = SimpleNamespace(
            clock_in=datetime(2026, 9, 21, 8, 50),
            clock_out=datetime(2026, 9, 21, 17, 30),
        )
        assert AttendanceService._evaluate_status(rec) == "EARLY"

    def test_late_and_early(self):
        rec = SimpleNamespace(
            clock_in=datetime(2026, 9, 21, 9, 20),
            clock_out=datetime(2026, 9, 21, 17, 0),
        )
        assert AttendanceService._evaluate_status(rec) == "LATE_EARLY"


class TestClockFlow:
    """打卡流程：上班打卡 → 下班签退 → 重复打卡报错"""

    def test_clock_in_then_out_then_reject(self, db, roles):
        user = _make_user(db, roles)

        # 第一次：上班打卡
        r1 = AttendanceService.clock(db, user)
        assert r1["type"] == "clock_in"

        # 第二次：下班签退
        r2 = AttendanceService.clock(db, user)
        assert r2["type"] == "clock_out"

        # 第三次：当日已完成，拒绝
        with pytest.raises(ValidationException):
            AttendanceService.clock(db, user)

    def test_my_records_returns_stats(self, db, roles):
        user = _make_user(db, roles)
        AttendanceService.clock(db, user)
        AttendanceService.clock(db, user)

        month = datetime.now().strftime("%Y-%m")
        result = AttendanceService.my_records(db, user, month)
        assert result["stats"]["days"] == 1
        assert len(result["items"]) == 1

    def test_invalid_month_format(self, db, roles):
        user = _make_user(db, roles)
        with pytest.raises(ValidationException):
            AttendanceService.my_records(db, user, "2026/09")
