# ============================================================
# SQLAlchemy 数据模型 - 考勤（简化版）
# 每人每天一条记录：上班打卡（clock_in）/ 下班签退（clock_out）
# status 由打卡时间与上下班规则（配置）比较得出：
#   NORMAL 正常 / LATE 迟到 / EARLY 早退 / LATE_EARLY 迟到且早退
# ============================================================

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.sqlite import Base
from app.models.user import utcnow


class AttendanceRecord(Base):
    """考勤记录表（每人每天一条）"""
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True, comment="员工ID"
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="工作日期")
    clock_in: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="上班打卡时间"
    )
    clock_out: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="下班签退时间"
    )
    status: Mapped[str] = mapped_column(
        String(16), default="NORMAL", nullable=False, comment="考勤状态"
    )
    source: Mapped[str] = mapped_column(
        String(16), default="web", comment="打卡来源（web）"
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    def __repr__(self):
        return f"<AttendanceRecord(user_id={self.user_id}, date={self.work_date}, status='{self.status}')>"
