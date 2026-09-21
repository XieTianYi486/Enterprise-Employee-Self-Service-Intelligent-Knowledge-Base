# ============================================================
# 考勤服务（简化版）
# 规则：上班时间前打卡=正常，超过上班时间=迟到；
#       下班时间后签退=正常，早于下班时间=早退
# 每人每天一条记录；上下班时间从配置读取
# ============================================================

from datetime import datetime, date, time as dtime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ValidationException
from app.models.user import User
from app.models.attendance import AttendanceRecord


class AttendanceService:
    """考勤业务逻辑（简化版打卡）"""

    STATUS_NORMAL = "NORMAL"
    STATUS_LATE = "LATE"
    STATUS_EARLY = "EARLY"
    STATUS_LATE_EARLY = "LATE_EARLY"

    @staticmethod
    def _work_start() -> dtime:
        return dtime(settings.WORK_START_HOUR, settings.WORK_START_MINUTE)

    @staticmethod
    def _work_end() -> dtime:
        return dtime(settings.WORK_END_HOUR, settings.WORK_END_MINUTE)

    @staticmethod
    def _evaluate_status(record: AttendanceRecord) -> str:
        """按打卡/签退时间评定当日状态"""
        late = record.clock_in and record.clock_in.time() > AttendanceService._work_start()
        early = record.clock_out and record.clock_out.time() < AttendanceService._work_end()
        if late and early:
            return AttendanceService.STATUS_LATE_EARLY
        if late:
            return AttendanceService.STATUS_LATE
        if early:
            return AttendanceService.STATUS_EARLY
        return AttendanceService.STATUS_NORMAL

    @staticmethod
    def clock(db: Session, user: User) -> dict:
        """
        打卡（同一请求内自动判断上班打卡/下班签退）：
        - 当日无记录 → 记录上班打卡
        - 已打卡未签退 → 记录下班签退并评定当日状态
        - 已完成 → 报错（当日考勤已结束）
        """
        now = datetime.now()
        today = now.date()
        record = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.user_id == user.id,
                AttendanceRecord.work_date == today,
            )
            .first()
        )

        if record is None:
            record = AttendanceRecord(
                user_id=user.id, work_date=today, clock_in=now,
            )
            db.add(record)
            db.flush()
            return {
                "type": "clock_in", "time": str(now), "work_date": str(today),
                "status": AttendanceService._evaluate_status(record),
                "message": "上班打卡成功",
            }

        if record.clock_out is not None:
            raise ValidationException("今日已完成签到签退，无需重复打卡")

        record.clock_out = now
        record.status = AttendanceService._evaluate_status(record)
        db.flush()
        return {
            "type": "clock_out", "time": str(now), "work_date": str(today),
            "status": record.status,
            "message": "下班签退成功",
        }

    @staticmethod
    def my_records(db: Session, user: User, month: str) -> dict:
        """
        我的月度考勤：每日记录 + 汇总（打卡天数/迟到/早退）
        month: yyyy-MM
        """
        try:
            parsed = datetime.strptime(month, "%Y-%m")
        except (ValueError, TypeError):
            raise ValidationException("月份格式应为 yyyy-MM")
        year, mon = parsed.year, parsed.month

        start = date(year, mon, 1)
        if mon == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, mon + 1, 1)

        records = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.user_id == user.id,
                AttendanceRecord.work_date >= start,
                AttendanceRecord.work_date < end,
            )
            .order_by(AttendanceRecord.work_date.desc())
            .all()
        )

        late_count = sum(
            1 for r in records if r.status in ("LATE", "LATE_EARLY")
        )
        early_count = sum(
            1 for r in records if r.status in ("EARLY", "LATE_EARLY")
        )
        items = [
            {
                "work_date": str(r.work_date),
                "clock_in": str(r.clock_in) if r.clock_in else None,
                "clock_out": str(r.clock_out) if r.clock_out else None,
                "status": r.status,
            }
            for r in records
        ]
        return {
            "month": month,
            "stats": {
                "days": len(records),
                "late": late_count,
                "early": early_count,
            },
            "items": items,
        }

    @staticmethod
    def dept_records(db: Session, dept_id: int, month: str) -> list[dict]:
        """
        部门月度考勤（部门管理员/总经理/超管）：按员工汇总
        """
        try:
            parsed = datetime.strptime(month, "%Y-%m")
        except (ValueError, TypeError):
            raise ValidationException("月份格式应为 yyyy-MM")
        year, mon = parsed.year, parsed.month

        start = date(year, mon, 1)
        if mon == 12:
            end = date(year + 1, 1, 1)
        else:
            end = date(year, mon + 1, 1)

        q = db.query(User).filter(User.status == 1)
        if dept_id is not None:
            q = q.filter(User.dept_id == dept_id)
        users = q.all()

        result = []
        for u in users:
            records = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.user_id == u.id,
                    AttendanceRecord.work_date >= start,
                    AttendanceRecord.work_date < end,
                )
                .all()
            )
            late = sum(1 for r in records if r.status in ("LATE", "LATE_EARLY"))
            early = sum(1 for r in records if r.status in ("EARLY", "LATE_EARLY"))
            result.append({
                "user_id": u.id,
                "real_name": u.real_name or u.username,
                "dept_name": u.dept.name if u.dept else None,
                "days": len(records),
                "late": late,
                "early": early,
            })
        return result
