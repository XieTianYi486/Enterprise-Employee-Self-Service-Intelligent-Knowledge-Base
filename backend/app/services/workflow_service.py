# ============================================================
# OA 办公流程服务层（审批引擎）
# 请假 / 报销 / 假期余额 / 两级审批状态机
#
# 审批状态机（请假与报销共用，仅阈值不同）：
#   PENDING → APPROVED / REJECTED；PENDING → CANCELLED（仅申请人本人）
# 起始节点（按申请人角色）：
#   超级管理员 / 总经理   → NONE（免审，提交即通过）
#   部门管理员（部门经理） → BOSS（本人申请跳过经理节点，直达总经理）
#   其他（员工等）         → MANAGER（部门经理先审）
# 阈值升级（配置项）：
#   请假天数 > LEAVE_BOSS_APPROVAL_DAYS → 经理通过后升级总经理终审
#   报销金额 > EXPENSE_BOSS_APPROVAL_AMOUNT → 同上
# ============================================================

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    PermissionDeniedException,
)
from app.models.user import User
from app.models.workflow import (
    LeaveBalance, LeaveRequest, ExpenseRequest, ApprovalRecord,
)


class WorkflowService:
    """OA 办公流程业务逻辑（审批引擎）"""

    # ==================== 业务常量 ====================
    LEAVE_TYPES = ("年假", "事假", "病假", "调休", "婚假")
    EXPENSE_TYPES = ("差旅费", "办公用品", "招待费", "交通费", "其他")

    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CANCELLED = "CANCELLED"

    NODE_NONE = "NONE"
    NODE_MANAGER = "MANAGER"
    NODE_BOSS = "BOSS"

    BIZ_LEAVE = "LEAVE"
    BIZ_EXPENSE = "EXPENSE"

    # ==================== 假期余额 ====================

    @staticmethod
    def ensure_balance(db: Session, user_id: int, year: int) -> LeaveBalance:
        """获取（不存在则创建）指定年份的假期余额记录"""
        bal = (
            db.query(LeaveBalance)
            .filter(LeaveBalance.user_id == user_id, LeaveBalance.year == year)
            .first()
        )
        if bal is None:
            bal = LeaveBalance(user_id=user_id, year=year)
            db.add(bal)
            db.flush()
        return bal

    @staticmethod
    def get_balance(db: Session, user_id: int, year: int = None) -> dict:
        """查询假期余额（默认当年）"""
        year = year or datetime.now().year
        bal = WorkflowService.ensure_balance(db, user_id, year)
        return {
            "year": bal.year,
            "annual_total": bal.annual_total,
            "annual_used": bal.annual_used,
            "annual_left": round(bal.annual_total - bal.annual_used, 1),
            "personal_used": bal.personal_used,
            "sick_used": bal.sick_used,
            "compensatory_total": bal.compensatory_total,
            "compensatory_used": bal.compensatory_used,
            "compensatory_left": round(bal.compensatory_total - bal.compensatory_used, 1),
        }

    # ==================== 起始节点计算 ====================

    @staticmethod
    def start_node_for(user: User) -> str:
        """
        按申请人角色计算起始审批节点。

        规则（参考业界通用两级审批实践，参考项目同类规则）：
        - 超级管理员 / 总经理：免审，提交即通过；
        - 部门管理员（部门经理）：本人申请跳过经理节点，直达总经理；
        - 其他角色（普通员工、知识库管理员等）：先经部门经理审批。
        """
        role_code = user.role.code if user.role else "employee"
        if role_code in ("super_admin", "boss"):
            return WorkflowService.NODE_NONE
        if role_code == "dept_admin":
            return WorkflowService.NODE_BOSS
        return WorkflowService.NODE_MANAGER

    @staticmethod
    def _exceeds_threshold(bill) -> bool:
        """判断经理节点通过后是否需要升级总经理终审（阈值取自配置）"""
        if isinstance(bill, LeaveRequest):
            return bill.days > settings.LEAVE_BOSS_APPROVAL_DAYS
        return bill.amount > settings.EXPENSE_BOSS_APPROVAL_AMOUNT

    @staticmethod
    def _deduct_leave_balance(db: Session, bill: LeaveRequest) -> None:
        """审批通过后按请假类型扣减当年余额（年假/事假/病假/调休；婚假不扣减）"""
        if bill.leave_type == "婚假":
            return
        bal = WorkflowService.ensure_balance(db, bill.user_id, bill.start_date.year)
        if bill.leave_type == "年假":
            bal.annual_used += bill.days
        elif bill.leave_type == "事假":
            bal.personal_used += bill.days
        elif bill.leave_type == "病假":
            bal.sick_used += bill.days
        elif bill.leave_type == "调休":
            bal.compensatory_used += bill.days

    # ==================== 请假 ====================

    @staticmethod
    def submit_leave(db: Session, user: User, data) -> LeaveRequest:
        """提交请假申请"""
        if data.leave_type not in WorkflowService.LEAVE_TYPES:
            raise ValidationException(f"请假类型必须是：{'/'.join(WorkflowService.LEAVE_TYPES)}")

        try:
            start_date = datetime.strptime(data.start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(data.end_date, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationException("日期格式应为 yyyy-MM-dd")

        if end_date < start_date:
            raise ValidationException("结束日期不能早于开始日期")

        days = (end_date - start_date).days + 1  # 含首尾两天

        # 额度校验：年假/调休申请不能超过当前余额
        bal = WorkflowService.ensure_balance(db, user.id, start_date.year)
        if data.leave_type == "年假" and days > bal.annual_total - bal.annual_used:
            raise ValidationException(
                f"年假余额不足（剩余 {round(bal.annual_total - bal.annual_used, 1)} 天）"
            )
        if data.leave_type == "调休" and days > bal.compensatory_total - bal.compensatory_used:
            raise ValidationException(
                f"调休余额不足（剩余 {round(bal.compensatory_total - bal.compensatory_used, 1)} 天）"
            )

        node = WorkflowService.start_node_for(user)
        bill = LeaveRequest(
            user_id=user.id,
            dept_id=user.dept_id,
            leave_type=data.leave_type,
            start_date=start_date,
            end_date=end_date,
            days=float(days),
            reason=data.reason,
            status=WorkflowService.STATUS_APPROVED if node == WorkflowService.NODE_NONE
                   else WorkflowService.STATUS_PENDING,
            current_node=node,
        )
        db.add(bill)
        db.flush()

        # 免审直接通过时同步扣减余额（保证额度闭环）
        if node == WorkflowService.NODE_NONE:
            WorkflowService._deduct_leave_balance(db, bill)

        return bill

    # ==================== 报销 ====================

    @staticmethod
    def submit_expense(db: Session, user: User, data) -> ExpenseRequest:
        """提交报销申请"""
        if data.expense_type not in WorkflowService.EXPENSE_TYPES:
            raise ValidationException(f"报销类型必须是：{'/'.join(WorkflowService.EXPENSE_TYPES)}")

        try:
            expense_date = datetime.strptime(data.expense_date, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationException("日期格式应为 yyyy-MM-dd")

        if data.amount <= 0:
            raise ValidationException("报销金额必须大于 0")

        node = WorkflowService.start_node_for(user)
        bill = ExpenseRequest(
            user_id=user.id,
            dept_id=user.dept_id,
            expense_type=data.expense_type,
            amount=data.amount,
            expense_date=expense_date,
            reason=data.reason,
            attachments=data.attachments or [],
            status=WorkflowService.STATUS_APPROVED if node == WorkflowService.NODE_NONE
                   else WorkflowService.STATUS_PENDING,
            current_node=node,
        )
        db.add(bill)
        db.flush()
        return bill

    # ==================== 撤销 ====================

    @staticmethod
    def cancel(db: Session, biz_type: str, biz_id: int, user: User) -> None:
        """撤销单据（仅申请人本人、且仅待审批状态）"""
        bill = WorkflowService._get_bill(db, biz_type, biz_id, for_update=True)
        if bill.user_id != user.id:
            raise PermissionDeniedException("只能撤销本人提交的单据")
        if bill.status != WorkflowService.STATUS_PENDING:
            raise ValidationException("仅待审批的单据可以撤销")
        bill.status = WorkflowService.STATUS_CANCELLED
        bill.current_node = WorkflowService.NODE_NONE
        db.flush()

    # ==================== 审批引擎（核心） ====================

    @staticmethod
    def _get_bill(db: Session, biz_type: str, biz_id: int, for_update: bool = False):
        """
        按业务类型获取单据。

        for_update=True 时加行级锁（SELECT ... FOR UPDATE）：
        SQLite 下无副作用，MySQL 生产环境下可防止并发双审
        （检查-后-写 TOCTOU）导致的重复扣减假期余额。
        """
        model = LeaveRequest if biz_type == WorkflowService.BIZ_LEAVE else ExpenseRequest
        q = db.query(model).filter(model.id == biz_id)
        if for_update:
            q = q.with_for_update()
        bill = q.first()
        if bill is None:
            raise NotFoundException("单据不存在")
        return bill

    @staticmethod
    def _check_node_permission(bill, approver: User) -> None:
        """
        节点审批权限校验：
        - BOSS 节点：仅总经理（super_admin 特权放行）
        - MANAGER 节点：仅部门管理员，且只能审批本部门单据（super_admin 特权放行）
        """
        role_code = approver.role.code if approver.role else ""
        if role_code == "super_admin":
            return
        if bill.current_node == WorkflowService.NODE_BOSS:
            if role_code != "boss":
                raise PermissionDeniedException("仅总经理可审批该节点")
        elif bill.current_node == WorkflowService.NODE_MANAGER:
            if role_code != "dept_admin":
                raise PermissionDeniedException("仅部门管理员可审批该节点")
            # 本部门校验：申请人无部门时不设限（兜底，避免单据滞留）
            if bill.dept_id is not None and approver.dept_id != bill.dept_id:
                raise PermissionDeniedException("只能审批本部门的单据")

    @staticmethod
    def approve(
        db: Session, biz_type: str, biz_id: int,
        action: str, comment: str, approver: User,
    ) -> dict:
        """
        审批动作（同一事务内完成：校验 → 写流水 → 状态推进 → 余额扣减）

        返回: 审批后的单据状态信息
        """
        if action not in ("APPROVE", "REJECT"):
            raise ValidationException("审批动作必须是 APPROVE 或 REJECT")

        # 行级锁：防并发双审（见 _get_bill 说明）
        bill = WorkflowService._get_bill(db, biz_type, biz_id, for_update=True)
        if bill.status != WorkflowService.STATUS_PENDING:
            raise ValidationException("该单据已处理，无需重复审批")

        WorkflowService._check_node_permission(bill, approver)

        # 1. 写入审批流水（全程留痕）
        db.add(ApprovalRecord(
            biz_type=biz_type,
            biz_id=bill.id,
            node_name=bill.current_node,
            approver_id=approver.id,
            approver_role=approver.role.code if approver.role else "",
            action_type=action,
            comment_text=comment,
        ))

        # 2. 驳回：关闭单据
        if action == "REJECT":
            bill.status = WorkflowService.STATUS_REJECTED
            bill.current_node = WorkflowService.NODE_NONE
            db.flush()
            return {
                "status": bill.status, "current_node": bill.current_node,
                "user_id": bill.user_id,
            }

        # 3. 通过：经理节点且超阈值 → 升级总经理终审
        if (bill.current_node == WorkflowService.NODE_MANAGER
                and WorkflowService._exceeds_threshold(bill)):
            bill.current_node = WorkflowService.NODE_BOSS
            db.flush()
            return {
                "status": bill.status, "current_node": bill.current_node,
                "user_id": bill.user_id,
            }

        # 4. 通过：流程结束（请假同步扣减余额）
        bill.status = WorkflowService.STATUS_APPROVED
        bill.current_node = WorkflowService.NODE_NONE
        if biz_type == WorkflowService.BIZ_LEAVE:
            WorkflowService._deduct_leave_balance(db, bill)
        db.flush()
        return {
            "status": bill.status, "current_node": bill.current_node,
            "user_id": bill.user_id,
        }

    # ==================== 列表查询（按角色数据范围） ====================

    @staticmethod
    def list_bills(
        db: Session, biz_type: str, user: User,
        page: int = 1, page_size: int = 20,
        status: str = None, pending_only: bool = False,
    ) -> dict:
        """
        分页查询单据，按角色收缩数据范围：
        - 普通员工/知识库管理员：仅本人
        - 部门管理员：本人 + 本部门
        - 总经理/超级管理员：全部
        pending_only=True 时仅返回待办：
        - 部门管理员：本部门 MANAGER 节点
        - 总经理：BOSS 节点
        - 超级管理员：全部 PENDING
        """
        model = LeaveRequest if biz_type == WorkflowService.BIZ_LEAVE else ExpenseRequest
        role_code = user.role.code if user.role else "employee"

        q = db.query(model)
        if role_code in ("employee", "knowledge_admin"):
            q = q.filter(model.user_id == user.id)
        elif role_code == "dept_admin":
            q = q.filter(
                (model.user_id == user.id) |
                (model.dept_id.isnot(None) & (model.dept_id == user.dept_id))
            )
        # boss / super_admin：不过滤（全部可见）

        if pending_only:
            if role_code == "dept_admin":
                q = q.filter(
                    model.status == WorkflowService.STATUS_PENDING,
                    model.current_node == WorkflowService.NODE_MANAGER,
                    model.dept_id.isnot(None),
                    model.dept_id == user.dept_id,
                )
            elif role_code == "boss":
                q = q.filter(
                    model.status == WorkflowService.STATUS_PENDING,
                    model.current_node == WorkflowService.NODE_BOSS,
                )
            elif role_code == "super_admin":
                q = q.filter(model.status == WorkflowService.STATUS_PENDING)
            else:
                q = q.filter(
                    model.status == WorkflowService.STATUS_PENDING,
                    model.user_id == user.id,
                )
        elif status:
            q = q.filter(model.status == status)

        total = q.count()
        bills = q.order_by(model.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

        # 申请人姓名映射（一次查询，避免 N+1）
        user_ids = {b.user_id for b in bills}
        name_map = WorkflowService._user_name_map(db, user_ids)

        items = []
        for b in bills:
            items.append(WorkflowService._bill_to_dict(b, name_map.get(b.user_id)))

        return {"total": total, "page": page, "page_size": page_size, "items": items}

    @staticmethod
    def get_bill_detail(db: Session, biz_type: str, biz_id: int, user: User) -> dict:
        """单据详情（含审批流水时间线）"""
        bill = WorkflowService._get_bill(db, biz_type, biz_id)
        role_code = user.role.code if user.role else "employee"
        # 数据范围：员工仅本人；部门管理员限本部门；总经理/超管全部
        if role_code in ("employee", "knowledge_admin") and bill.user_id != user.id:
            raise PermissionDeniedException("无权查看该单据")
        if (role_code == "dept_admin" and bill.user_id != user.id
                and (bill.dept_id is None or bill.dept_id != user.dept_id)):
            raise PermissionDeniedException("无权查看该单据")

        records = (
            db.query(ApprovalRecord)
            .filter(
                ApprovalRecord.biz_type == biz_type,
                ApprovalRecord.biz_id == biz_id,
            )
            .order_by(ApprovalRecord.id.asc())
            .all()
        )
        approver_ids = {r.approver_id for r in records}
        name_map = WorkflowService._user_name_map(db, approver_ids | {bill.user_id})

        detail = WorkflowService._bill_to_dict(bill, name_map.get(bill.user_id))
        detail["records"] = [
            {
                "node_name": r.node_name,
                "approver_name": name_map.get(r.approver_id),
                "approver_role": r.approver_role,
                "action_type": r.action_type,
                "comment_text": r.comment_text,
                "create_time": str(r.create_time),
            }
            for r in records
        ]
        return detail

    @staticmethod
    def _bill_to_dict(bill, applicant_name: str = None) -> dict:
        """单据序列化（请假与报销字段并集，另一方缺失字段置空）"""
        if isinstance(bill, LeaveRequest):
            return {
                "id": bill.id,
                "biz_type": WorkflowService.BIZ_LEAVE,
                "user_id": bill.user_id,
                "applicant_name": applicant_name,
                "dept_id": bill.dept_id,
                "leave_type": bill.leave_type,
                "start_date": str(bill.start_date),
                "end_date": str(bill.end_date),
                "days": bill.days,
                "reason": bill.reason,
                "expense_type": None,
                "amount": None,
                "expense_date": None,
                "attachments": None,
                "status": bill.status,
                "current_node": bill.current_node,
                "create_time": str(bill.create_time),
            }
        return {
            "id": bill.id,
            "biz_type": WorkflowService.BIZ_EXPENSE,
            "user_id": bill.user_id,
            "applicant_name": applicant_name,
            "dept_id": bill.dept_id,
            "leave_type": None,
            "start_date": None,
            "end_date": None,
            "days": None,
            "reason": bill.reason,
            "expense_type": bill.expense_type,
            "amount": bill.amount,
            "expense_date": str(bill.expense_date),
            "attachments": bill.attachments,
            "status": bill.status,
            "current_node": bill.current_node,
            "create_time": str(bill.create_time),
        }

    @staticmethod
    def _user_name_map(db: Session, user_ids: set) -> dict:
        """批量查询用户姓名映射"""
        if not user_ids:
            return {}
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        return {u.id: u.real_name or u.username for u in users}
