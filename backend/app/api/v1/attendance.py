# ============================================================
# 考勤接口（简化版）
# 员工：打卡 / 我的月度考勤
# 管理（部门管理员/总经理/超管）：部门月度考勤汇总
# ============================================================

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.sqlite import get_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.schemas.common import APIResponse
from app.services.attendance_service import AttendanceService
from app.services.audit_service import add_audit_log

router = APIRouter(tags=["考勤"])


@router.post("/attendance/clock", response_model=APIResponse, summary="打卡/签退")
def clock(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """当日首次调用=上班打卡，第二次=下班签退（服务端时间）"""
    result = AttendanceService.clock(db, current_user)
    add_audit_log(
        db=db, module="attendance", action=f"attendance_{result['type']}", status="success",
        user_id=current_user.id, username=current_user.username,
        detail={"status": result["status"]},
    )
    return APIResponse(code=0, message=result["message"], data=result)


@router.get("/attendance/my", response_model=APIResponse, summary="我的月度考勤")
def my_attendance(
    month: str = Query(..., description="月份 yyyy-MM"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """我的月度考勤记录与汇总"""
    return APIResponse(
        code=0, message="success",
        data=AttendanceService.my_records(db, current_user, month)
    )


@router.get("/admin/attendance", response_model=APIResponse, summary="部门考勤汇总")
def dept_attendance(
    month: str = Query(..., description="月份 yyyy-MM"),
    dept_id: Optional[int] = Query(default=None, description="部门ID（不传=全部部门）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """部门月度考勤汇总（部门管理员仅能查本部门，总经理/超管可查全部）"""
    role_code = current_user.role.code if current_user.role else "employee"
    if role_code not in ("super_admin", "boss", "dept_admin"):
        from app.core.exceptions import PermissionDeniedException
        raise PermissionDeniedException("无权查看部门考勤")

    # 部门管理员只能看本部门
    if role_code == "dept_admin":
        dept_id = current_user.dept_id

    return APIResponse(
        code=0, message="success",
        data=AttendanceService.dept_records(db, dept_id, month)
    )
