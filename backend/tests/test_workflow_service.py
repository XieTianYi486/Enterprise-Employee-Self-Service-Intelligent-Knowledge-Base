# ============================================================
# OA 办公流程服务单元测试（审批引擎）
# 覆盖：起始节点计算 / 请假校验 / 两级审批状态机 / 阈值升级 /
#       节点权限与数据范围 / 撤销规则 / 假期余额扣减
# ============================================================

import uuid
from datetime import date, timedelta

import pytest

from app.core.exceptions import (
    ValidationException,
    PermissionDeniedException,
)
from app.core.security import hash_password
from app.models.user import User, Department
from app.models.workflow import LeaveBalance, LeaveRequest, ExpenseRequest, ApprovalRecord
from app.services.workflow_service import WorkflowService


# ==================== 测试辅助 ====================

def _make_user(db, roles, code, dept=None):
    """创建指定角色的测试用户（用户名带随机后缀避免唯一键冲突）"""
    user = User(
        username=f"{code}_{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("test123456"),
        role_id=roles[code].id,
        dept_id=dept.id if dept else None,
    )
    db.add(user)
    db.flush()
    return user


def _make_dept(db, name="测试部门"):
    dept = Department(name=f"{name}_{uuid.uuid4().hex[:6]}")
    db.add(dept)
    db.flush()
    return dept


def _leave_payload(start=None, end=None, leave_type="事假", reason="测试"):
    """构造请假请求（SimpleNamespace 模拟 Pydantic 请求对象）"""
    from types import SimpleNamespace
    today = date.today()
    return SimpleNamespace(
        leave_type=leave_type,
        start_date=(start or today).isoformat(),
        end_date=(end or today).isoformat(),
        reason=reason,
    )


def _expense_payload(amount=100.0, expense_type="办公用品"):
    from types import SimpleNamespace
    return SimpleNamespace(
        expense_type=expense_type,
        amount=amount,
        expense_date=date.today().isoformat(),
        reason="测试报销",
        attachments=[],
    )


# ==================== 起始节点计算 ====================

class TestStartNode:
    """起始审批节点规则：管理员/总经理免审、经理直达总经理、员工先经经理"""

    def test_employee_starts_at_manager(self, db, roles):
        dept = _make_dept(db)
        user = _make_user(db, roles, "employee", dept)
        assert WorkflowService.start_node_for(user) == "MANAGER"

    def test_dept_admin_skips_manager_to_boss(self, db, roles):
        dept = _make_dept(db)
        user = _make_user(db, roles, "dept_admin", dept)
        assert WorkflowService.start_node_for(user) == "BOSS"

    def test_boss_and_super_admin_auto_pass(self, db, roles):
        boss = _make_user(db, roles, "boss")
        super_admin = _make_user(db, roles, "super_admin")
        assert WorkflowService.start_node_for(boss) == "NONE"
        assert WorkflowService.start_node_for(super_admin) == "NONE"

    def test_knowledge_admin_starts_at_manager(self, db, roles):
        dept = _make_dept(db)
        user = _make_user(db, roles, "knowledge_admin", dept)
        assert WorkflowService.start_node_for(user) == "MANAGER"


# ==================== 请假提交校验 ====================

class TestSubmitLeave:
    """请假提交：类型/日期/余额校验，节点与状态初始化"""

    def test_invalid_leave_type_rejected(self, db, roles):
        user = _make_user(db, roles, "employee")
        payload = _leave_payload(leave_type="旷工")
        with pytest.raises(ValidationException):
            WorkflowService.submit_leave(db, user, payload)

    def test_end_before_start_rejected(self, db, roles):
        user = _make_user(db, roles, "employee")
        payload = _leave_payload(
            start=date.today(), end=date.today() - timedelta(days=1)
        )
        with pytest.raises(ValidationException):
            WorkflowService.submit_leave(db, user, payload)

    def test_insufficient_annual_balance_rejected(self, db, roles):
        user = _make_user(db, roles, "employee")
        # 默认年假总额 5 天，申请 6 天应被拒绝
        payload = _leave_payload(
            start=date.today(),
            end=date.today() + timedelta(days=5),
            leave_type="年假",
        )
        with pytest.raises(ValidationException, match="余额不足"):
            WorkflowService.submit_leave(db, user, payload)

    def test_employee_submit_pending_at_manager(self, db, roles):
        dept = _make_dept(db)
        user = _make_user(db, roles, "employee", dept)
        payload = _leave_payload(
            start=date.today(), end=date.today() + timedelta(days=1)
        )
        bill = WorkflowService.submit_leave(db, user, payload)
        assert bill.status == "PENDING"
        assert bill.current_node == "MANAGER"
        assert bill.days == 2  # 含首尾两天
        assert bill.dept_id == dept.id

    def test_boss_submit_auto_approved_and_deducts(self, db, roles):
        user = _make_user(db, roles, "boss")
        payload = _leave_payload(
            start=date.today(), end=date.today(), leave_type="年假"
        )
        bill = WorkflowService.submit_leave(db, user, payload)
        assert bill.status == "APPROVED"
        assert bill.current_node == "NONE"
        # 免审直接通过也要扣减余额
        bal = WorkflowService.ensure_balance(db, user.id, date.today().year)
        assert bal.annual_used == 1.0


# ==================== 两级审批状态机 ====================

class TestApproveLeave:
    """审批引擎：短假直达通过、长假升级总经理、驳回关闭、余额扣减"""

    def test_short_leave_manager_approve_finishes_and_deducts(self, db, roles):
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        mgr = _make_user(db, roles, "dept_admin", dept)
        payload = _leave_payload(
            start=date.today(), end=date.today() + timedelta(days=2), leave_type="事假"
        )
        bill = WorkflowService.submit_leave(db, emp, payload)

        result = WorkflowService.approve(
            db, "LEAVE", bill.id, "APPROVE", "同意", mgr
        )
        assert result["status"] == "APPROVED"
        assert result["current_node"] == "NONE"

        bal = WorkflowService.ensure_balance(db, emp.id, date.today().year)
        assert bal.personal_used == 3.0  # 事假扣减

        records = db.query(ApprovalRecord).filter(ApprovalRecord.biz_id == bill.id).all()
        assert len(records) == 1
        assert records[0].node_name == "MANAGER"

    def test_long_leave_escalates_to_boss(self, db, roles):
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        mgr = _make_user(db, roles, "dept_admin", dept)
        boss = _make_user(db, roles, "boss")
        # 5 天年假 > 阈值 3 天
        payload = _leave_payload(
            start=date.today(), end=date.today() + timedelta(days=4), leave_type="年假"
        )
        bill = WorkflowService.submit_leave(db, emp, payload)

        # 经理通过 → 升级总经理节点，流程未结束
        result = WorkflowService.approve(db, "LEAVE", bill.id, "APPROVE", "同意", mgr)
        assert result["status"] == "PENDING"
        assert result["current_node"] == "BOSS"

        # 总经理终审通过 → 流程结束，扣减年假
        result = WorkflowService.approve(db, "LEAVE", bill.id, "APPROVE", "批准", boss)
        assert result["status"] == "APPROVED"
        bal = WorkflowService.ensure_balance(db, emp.id, date.today().year)
        assert bal.annual_used == 5.0

        records = db.query(ApprovalRecord).filter(ApprovalRecord.biz_id == bill.id).all()
        assert len(records) == 2  # 两级各一条流水

    def test_reject_closes_bill(self, db, roles):
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        mgr = _make_user(db, roles, "dept_admin", dept)
        bill = WorkflowService.submit_leave(db, emp, _leave_payload())

        result = WorkflowService.approve(db, "LEAVE", bill.id, "REJECT", "不同意", mgr)
        assert result["status"] == "REJECTED"
        assert result["current_node"] == "NONE"
        # 驳回不扣减余额
        bal = WorkflowService.ensure_balance(db, emp.id, date.today().year)
        assert bal.personal_used == 0.0

    def test_dept_admin_submit_goes_straight_to_boss(self, db, roles):
        dept = _make_dept(db)
        mgr = _make_user(db, roles, "dept_admin", dept)
        boss = _make_user(db, roles, "boss")
        bill = WorkflowService.submit_leave(db, mgr, _leave_payload(leave_type="病假"))
        assert bill.current_node == "BOSS"

        result = WorkflowService.approve(db, "LEAVE", bill.id, "APPROVE", "批准", boss)
        assert result["status"] == "APPROVED"


# ==================== 节点权限与数据范围 ====================

class TestApprovalPermission:
    """审批权限：跨部门拒绝、角色不符拒绝、重复审批拒绝"""

    def test_cross_department_manager_denied(self, db, roles):
        dept_a = _make_dept(db, "部门A")
        dept_b = _make_dept(db, "部门B")
        emp = _make_user(db, roles, "employee", dept_a)
        other_mgr = _make_user(db, roles, "dept_admin", dept_b)
        bill = WorkflowService.submit_leave(db, emp, _leave_payload())

        with pytest.raises(PermissionDeniedException):
            WorkflowService.approve(db, "LEAVE", bill.id, "APPROVE", "越权", other_mgr)

    def test_employee_cannot_approve(self, db, roles):
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        other = _make_user(db, roles, "employee", dept)
        bill = WorkflowService.submit_leave(db, emp, _leave_payload())

        with pytest.raises(PermissionDeniedException):
            WorkflowService.approve(db, "LEAVE", bill.id, "APPROVE", "", other)

    def test_boss_cannot_approve_manager_node(self, db, roles):
        """总经理只审 BOSS 节点，不能提前插手经理节点"""
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        boss = _make_user(db, roles, "boss")
        bill = WorkflowService.submit_leave(db, emp, _leave_payload())

        with pytest.raises(PermissionDeniedException):
            WorkflowService.approve(db, "LEAVE", bill.id, "APPROVE", "", boss)

    def test_super_admin_can_approve_any_node(self, db, roles):
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        admin = _make_user(db, roles, "super_admin")
        bill = WorkflowService.submit_leave(db, emp, _leave_payload())

        result = WorkflowService.approve(db, "LEAVE", bill.id, "APPROVE", "代批", admin)
        assert result["status"] == "APPROVED"

    def test_duplicate_approval_rejected(self, db, roles):
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        mgr = _make_user(db, roles, "dept_admin", dept)
        bill = WorkflowService.submit_leave(db, emp, _leave_payload())
        WorkflowService.approve(db, "LEAVE", bill.id, "APPROVE", "", mgr)

        with pytest.raises(ValidationException):
            WorkflowService.approve(db, "LEAVE", bill.id, "APPROVE", "", mgr)


# ==================== 撤销规则 ====================

class TestCancel:
    """撤销：仅本人、仅待审批"""

    def test_owner_can_cancel_pending(self, db, roles):
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        bill = WorkflowService.submit_leave(db, emp, _leave_payload())

        WorkflowService.cancel(db, "LEAVE", bill.id, emp)
        assert bill.status == "CANCELLED"
        assert bill.current_node == "NONE"

    def test_other_user_cannot_cancel(self, db, roles):
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        other = _make_user(db, roles, "employee", dept)
        bill = WorkflowService.submit_leave(db, emp, _leave_payload())

        with pytest.raises(PermissionDeniedException):
            WorkflowService.cancel(db, "LEAVE", bill.id, other)

    def test_processed_bill_cannot_cancel(self, db, roles):
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        mgr = _make_user(db, roles, "dept_admin", dept)
        bill = WorkflowService.submit_leave(db, emp, _leave_payload())
        WorkflowService.approve(db, "LEAVE", bill.id, "APPROVE", "", mgr)

        with pytest.raises(ValidationException):
            WorkflowService.cancel(db, "LEAVE", bill.id, emp)


# ==================== 报销（金额阈值） ====================

class TestExpenseApproval:
    """报销审批：小金额直达通过、超阈值升级总经理"""

    def test_small_expense_manager_approve_finishes(self, db, roles):
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        mgr = _make_user(db, roles, "dept_admin", dept)
        bill = WorkflowService.submit_expense(db, emp, _expense_payload(amount=100.0))

        result = WorkflowService.approve(db, "EXPENSE", bill.id, "APPROVE", "同意", mgr)
        assert result["status"] == "APPROVED"

    def test_large_expense_escalates_to_boss(self, db, roles):
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        mgr = _make_user(db, roles, "dept_admin", dept)
        boss = _make_user(db, roles, "boss")
        # 6500 元 > 阈值 5000 元
        bill = WorkflowService.submit_expense(db, emp, _expense_payload(amount=6500.0))

        result = WorkflowService.approve(db, "EXPENSE", bill.id, "APPROVE", "同意", mgr)
        assert result["status"] == "PENDING"
        assert result["current_node"] == "BOSS"

        result = WorkflowService.approve(db, "EXPENSE", bill.id, "APPROVE", "批准", boss)
        assert result["status"] == "APPROVED"

    def test_invalid_expense_type_rejected(self, db, roles):
        user = _make_user(db, roles, "employee")
        with pytest.raises(ValidationException):
            WorkflowService.submit_expense(db, user, _expense_payload(expense_type="吃喝玩乐"))


# ==================== 数据范围 ====================

class TestDataScope:
    """列表查询数据范围：员工仅本人、经理本部门、总经理全部"""

    def test_employee_sees_only_own(self, db, roles):
        dept = _make_dept(db)
        emp_a = _make_user(db, roles, "employee", dept)
        emp_b = _make_user(db, roles, "employee", dept)
        WorkflowService.submit_leave(db, emp_a, _leave_payload())
        WorkflowService.submit_leave(db, emp_b, _leave_payload())

        result = WorkflowService.list_bills(db, "LEAVE", emp_a)
        assert result["total"] == 1
        assert result["items"][0]["user_id"] == emp_a.id

    def test_manager_sees_department_bills(self, db, roles):
        dept_a = _make_dept(db, "部门A")
        dept_b = _make_dept(db, "部门B")
        emp_a = _make_user(db, roles, "employee", dept_a)
        emp_b = _make_user(db, roles, "employee", dept_b)
        mgr_a = _make_user(db, roles, "dept_admin", dept_a)
        WorkflowService.submit_leave(db, emp_a, _leave_payload())
        WorkflowService.submit_leave(db, emp_b, _leave_payload())

        result = WorkflowService.list_bills(db, "LEAVE", mgr_a)
        # 经理可见本部门单据（emp_a 的 1 条），不见其他部门（emp_b）
        assert result["total"] == 1
        assert result["items"][0]["user_id"] == emp_a.id

    def test_boss_sees_all_and_todo_by_node(self, db, roles):
        dept = _make_dept(db)
        emp = _make_user(db, roles, "employee", dept)
        mgr = _make_user(db, roles, "dept_admin", dept)
        boss = _make_user(db, roles, "boss")
        # 短假：经理节点；长假：经理通过后升级 BOSS 节点
        short_bill = WorkflowService.submit_leave(db, emp, _leave_payload())
        long_bill = WorkflowService.submit_leave(
            db, emp,
            _leave_payload(start=date.today(), end=date.today() + timedelta(days=4), leave_type="年假"),
        )
        WorkflowService.approve(db, "LEAVE", long_bill.id, "APPROVE", "", mgr)

        # 总经理待办只有 BOSS 节点单据
        todo = WorkflowService.list_bills(db, "LEAVE", boss, pending_only=True)
        assert todo["total"] == 1
        assert todo["items"][0]["id"] == long_bill.id

        # 经理待办只有本部门 MANAGER 节点单据
        mgr_todo = WorkflowService.list_bills(db, "LEAVE", mgr, pending_only=True)
        assert mgr_todo["total"] == 1
        assert mgr_todo["items"][0]["id"] == short_bill.id


# ==================== 假期余额 ====================

class TestBalance:
    """假期余额：惰性初始化与查询"""

    def test_ensure_balance_creates_defaults(self, db, roles):
        user = _make_user(db, roles, "employee")
        bal = WorkflowService.ensure_balance(db, user.id, date.today().year)
        assert bal.annual_total == 5.0
        assert bal.annual_used == 0.0
        assert bal.compensatory_total == 0.0

    def test_get_balance_returns_left_amounts(self, db, roles):
        user = _make_user(db, roles, "employee")
        info = WorkflowService.get_balance(db, user.id)
        assert info["annual_left"] == 5.0
        assert info["compensatory_left"] == 0.0
