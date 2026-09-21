# ============================================================
# 系统管理接口
# 用户管理、角色管理、问答日志、统计分析、系统配置
# ============================================================

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, desc
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.sqlite import get_db
from app.api.deps import (
    get_current_active_user,
    require_super_admin,
    require_knowledge_admin,
)
from app.models.user import User, Role, Department
from app.models.chat import ChatLog, ChatSession, ChatMessage
from app.models.document import Document
from app.models.announcement import Announcement
from app.schemas.common import APIResponse, PaginatedData
from app.schemas.auth import UserInfo

router = APIRouter(prefix="/admin", tags=["系统管理"])


# ==================== 权限码中文对照表 ====================
# 将代码化的权限点翻译为业务人员可理解的中文描述，
# 供角色管理页面展示，避免非技术用户看不懂权限码。

PERMISSION_LABELS = {
    "*": "全部权限",
    # 文档管理
    "documents:*": "文档管理（上传/编辑/删除/索引）",
    "documents:read": "查看文档",
    "docs:manage": "文档管理",
    # 分类管理
    "categories:*": "分类管理（创建/编辑/删除分类）",
    # 智能问答
    "chat:ask": "智能问答（向知识库提问）",
    "chat:history": "查看聊天历史",
    # 日志与统计
    "logs:read": "查看问答日志",
    "stats:read": "查看统计数据",
    "stats:view": "查看统计看板",
    "stats:dept": "查看本部门统计",
    # 办公流程（OA）
    "leaves:read": "查看请假单",
    "leaves:submit": "提交请假申请",
    "expenses:read": "查看报销单",
    "expenses:submit": "提交报销申请",
    "approvals:read": "查看审批待办",
    "approvals:approve": "审批单据",
}


def _translate_permissions(permissions) -> list[str]:
    """将权限码列表翻译为中文标签列表"""
    if not permissions:
        return []
    result = []
    for p in permissions:
        result.append(PERMISSION_LABELS.get(p, p))
    return result


# ==================== 用户管理 ====================

@router.get("/users", response_model=APIResponse, summary="用户列表")
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: Optional[str] = None,
    role_id: Optional[int] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """获取用户列表（仅超级管理员）"""
    # 使用 joinedload 预加载 role/dept，避免 N+1 查询和 detached instance 错误
    # 按 id 倒序（最新注册在前），确保新注册用户出现在第一页
    query = (
        db.query(User)
        .options(joinedload(User.role), joinedload(User.dept))
        .order_by(User.id.desc())
    )

    if keyword:
        query = query.filter(
            (User.username.contains(keyword)) |
            (User.real_name.contains(keyword)) |
            (User.email.contains(keyword))
        )
    if role_id is not None:
        query = query.filter(User.role_id == role_id)
    if status is not None:
        query = query.filter(User.status == status)

    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    user_list = []
    for u in users:
        user_list.append(UserInfo(
            id=u.id, username=u.username, real_name=u.real_name,
            email=u.email, phone=u.phone, avatar_url=u.avatar_url,
            position=u.position, department=u.dept.name if u.dept else None,
            dept_id=u.dept_id, gender=u.gender, entry_date=u.entry_date,
            role_id=u.role_id, role_name=u.role.name if u.role else None,
            status=u.status, created_at=u.created_at,
        ).model_dump())

    return APIResponse(
        code=0,
        message="success",
        data=PaginatedData.from_query(user_list, total, page, page_size).model_dump()
    )


@router.patch("/users/{user_id}/status", response_model=APIResponse, summary="启/禁用用户")
def toggle_user_status(
    user_id: int,
    status: int = Query(..., ge=0, le=1, description="0=禁用, 1=启用"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """启用或禁用用户账号"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return APIResponse(code=3001, message="用户不存在")
    if user.id == current_user.id:
        return APIResponse(code=3002, message="不能操作自己的账号")
    user.status = status
    db.flush()
    return APIResponse(code=0, message="操作成功")


@router.patch("/users/{user_id}/department", response_model=APIResponse, summary="修改用户部门")
def update_user_department(
    user_id: int,
    dept_id: int = Query(..., description="新部门ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """修改用户的所属部门（按部门ID）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return APIResponse(code=3001, message="用户不存在")
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        return APIResponse(code=3001, message="部门不存在")
    user.dept_id = dept_id
    db.flush()
    return APIResponse(code=0, message="部门更新成功")


@router.patch("/users/{user_id}/role", response_model=APIResponse, summary="修改用户角色")
def update_user_role(
    user_id: int,
    role_id: int = Query(..., ge=1, description="新角色ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """修改用户的角色（超级管理员专用）"""
    if user_id == current_user.id:
        return APIResponse(code=3002, message="不能修改自己的角色")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return APIResponse(code=3001, message="用户不存在")
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        return APIResponse(code=3001, message="角色不存在")
    user.role_id = role_id
    db.flush()
    # 重新加载 role 关系以便返回
    db.refresh(user)
    return APIResponse(code=0, message=f"角色已更新为: {role.name}")


# ==================== 角色管理 ====================

@router.get("/roles", response_model=APIResponse, summary="角色列表")
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """获取所有角色"""
    # 使用 selectinload 预加载 users，避免 lazy load 和 N+1 查询
    roles = db.query(Role).options(selectinload(Role.users)).all()
    data = [
        {
            "id": r.id, "name": r.name, "code": r.code,
            "description": r.description, "permissions": r.permissions,
            "permission_labels": _translate_permissions(r.permissions),
            "user_count": len(r.users),
        }
        for r in roles
    ]
    return APIResponse(code=0, message="success", data=data)


@router.post("/roles", response_model=APIResponse, summary="创建角色")
def create_role(
    name: str = Query(..., description="角色名称"),
    code: str = Query(..., description="角色编码（唯一标识）"),
    description: Optional[str] = Query(default=None, description="角色描述"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """创建新角色"""
    existing = db.query(Role).filter(Role.code == code).first()
    if existing:
        return APIResponse(code=3001, message="角色编码已存在")
    role = Role(
        name=name,
        code=code,
        description=description,
        permissions=[],
    )
    db.add(role)
    db.flush()
    db.refresh(role)
    return APIResponse(code=0, message="角色创建成功", data={
        "id": role.id, "name": role.name, "code": role.code,
    })


@router.put("/roles/{role_id}", response_model=APIResponse, summary="更新角色")
def update_role(
    role_id: int,
    name: Optional[str] = Query(default=None, description="角色名称"),
    description: Optional[str] = Query(default=None, description="角色描述"),
    permissions: Optional[str] = Query(default=None, description="权限列表（逗号分隔）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """更新角色信息（名称、描述、权限）"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        return APIResponse(code=3001, message="角色不存在")
    if name is not None:
        role.name = name
    if description is not None:
        role.description = description
    if permissions is not None:
        role.permissions = [p.strip() for p in permissions.split(",") if p.strip()]
    db.flush()
    return APIResponse(code=0, message="角色更新成功")


@router.delete("/roles/{role_id}", response_model=APIResponse, summary="删除角色")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """删除角色（仅当无用户关联时）"""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        return APIResponse(code=3001, message="角色不存在")
    user_count = db.query(User).filter(User.role_id == role_id).count()
    if user_count > 0:
        return APIResponse(code=3002, message=f"该角色下还有 {user_count} 名用户，无法删除")
    db.delete(role)
    db.flush()
    return APIResponse(code=0, message="角色已删除")


@router.delete("/users/{user_id}", response_model=APIResponse, summary="删除用户")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """删除用户账号（仅超级管理员）"""
    if user_id == current_user.id:
        return APIResponse(code=3003, message="不能删除当前登录账号")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return APIResponse(code=3001, message="用户不存在")

    # 清理关联数据，避免外键约束报错
    # 1. 删除用户的会话（会话消息通过 ORM cascade 自动删除）
    sessions = db.query(ChatSession).filter(ChatSession.user_id == user_id).all()
    for s in sessions:
        db.delete(s)
    # 2. 删除用户的问答日志
    db.query(ChatLog).filter(ChatLog.user_id == user_id).delete(synchronize_session=False)
    # 3. 置空用户上传的文档（保留文档，仅移除上传人关联）
    db.query(Document).filter(Document.created_by == user_id).update(
        {Document.created_by: None}, synchronize_session=False
    )
    # 4. 置空用户作为负责人的部门
    db.query(Department).filter(Department.manager_id == user_id).update(
        {Department.manager_id: None}, synchronize_session=False
    )

    db.delete(target)
    db.flush()
    return APIResponse(code=0, message="用户已删除")


# ==================== 问答日志 ====================

@router.get("/logs", response_model=APIResponse, summary="问答日志")
def list_chat_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: Optional[int] = None,
    keyword: Optional[str] = None,
    is_answered: Optional[int] = None,
    feedback: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """
    查询问答日志

    支持筛选：
    - user_id: 按用户筛选
    - keyword: 按问题关键词搜索
    - is_answered: 0=未命中, 1=命中
    - feedback: 0=未反馈, 1=点赞, 2=点踩
    - date_from / date_to: 日期范围 (YYYY-MM-DD)
    """
    query = db.query(ChatLog)

    if user_id:
        query = query.filter(ChatLog.user_id == user_id)
    if keyword:
        query = query.filter(
            (ChatLog.question.contains(keyword)) |
            (ChatLog.answer.contains(keyword))
        )
    if is_answered is not None:
        query = query.filter(ChatLog.is_answered == is_answered)
    if feedback is not None:
        query = query.filter(ChatLog.feedback == feedback)
    if date_from:
        query = query.filter(ChatLog.created_at >= f"{date_from}T00:00:00")
    if date_to:
        query = query.filter(ChatLog.created_at <= f"{date_to}T23:59:59")

    total = query.count()
    logs = query.order_by(ChatLog.created_at.desc()) \
        .offset((page - 1) * page_size).limit(page_size).all()

    log_list = [{
        "id": log.id,
        "session_id": log.session_id,
        "user_id": log.user_id,
        "question": log.question,
        "answer": (log.answer or "")[:300],  # 截断长回答用于列表展示
        "answer_full": log.answer or "",     # 完整回答
        "is_answered": log.is_answered,
        "feedback": log.feedback,
        "feedback_reason": log.feedback_reason,
        "source_doc_ids": log.source_doc_ids,
        "retrieval_ms": log.retrieval_ms,
        "rerank_ms": log.rerank_ms,
        "llm_ms": log.llm_ms,
        "total_ms": log.total_ms,
        "prompt_tokens": log.prompt_tokens,
        "completion_tokens": log.completion_tokens,
        "created_at": str(log.created_at),
    } for log in logs]

    return APIResponse(
        code=0,
        message="success",
        data=PaginatedData.from_query(log_list, total, page, page_size).model_dump()
    )


@router.get("/logs/{log_id}", response_model=APIResponse, summary="日志详情")
def get_chat_log_detail(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """查看单条问答日志的完整详情"""
    log = db.query(ChatLog).filter(ChatLog.id == log_id).first()
    if not log:
        return APIResponse(code=3001, message="日志不存在")

    # 查找用户名
    user = db.query(User).filter(User.id == log.user_id).first()

    return APIResponse(code=0, message="success", data={
        "id": log.id,
        "session_id": log.session_id,
        "user_id": log.user_id,
        "username": user.real_name or user.username if user else "未知",
        "question": log.question,
        "answer": log.answer or "",
        "is_answered": log.is_answered,
        "feedback": log.feedback,
        "feedback_reason": log.feedback_reason,
        "source_doc_ids": log.source_doc_ids,
        "retrieval_ms": log.retrieval_ms,
        "rerank_ms": log.rerank_ms,
        "llm_ms": log.llm_ms,
        "total_ms": log.total_ms,
        "prompt_tokens": log.prompt_tokens,
        "completion_tokens": log.completion_tokens,
        "created_at": str(log.created_at),
    })


@router.get("/stats/hot-questions", response_model=APIResponse, summary="高频问题排行")
def get_hot_questions(
    limit: int = Query(default=20, ge=5, le=100),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """获取高频问题 TOP N（按出现次数排序）"""
    query = db.query(
        ChatLog.question, func.count(ChatLog.id).label("count")
    ).filter(ChatLog.is_answered == 1)

    if date_from:
        query = query.filter(ChatLog.created_at >= f"{date_from}T00:00:00")
    if date_to:
        query = query.filter(ChatLog.created_at <= f"{date_to}T23:59:59")

    rows = query.group_by(ChatLog.question) \
        .order_by(desc("count")).limit(limit).all()

    data = [{"question": r[0], "count": r[1]} for r in rows]
    return APIResponse(code=0, message="success", data=data)


@router.get("/stats/unanswered", response_model=APIResponse, summary="未命中问题列表")
def get_unanswered_questions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """获取未命中（拒答）的问题列表，用于识别知识库盲区"""
    query = db.query(ChatLog).filter(ChatLog.is_answered == 0)
    total = query.count()
    logs = query.order_by(ChatLog.created_at.desc()) \
        .offset((page - 1) * page_size).limit(page_size).all()

    data = [{
        "id": log.id,
        "question": log.question,
        "user_id": log.user_id,
        "created_at": str(log.created_at),
    } for log in logs]

    return APIResponse(
        code=0, message="success",
        data=PaginatedData.from_query(data, total, page, page_size).model_dump()
    )


# ==================== 统计分析 ====================

@router.get("/stats/overview", response_model=APIResponse, summary="系统统计概览")
def get_system_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """获取系统级统计数据"""
    user_count = db.query(User).filter(User.status == 1).count()
    session_count = db.query(ChatSession).count()
    message_count = db.query(ChatMessage).count()
    log_count = db.query(ChatLog).count()
    answered_count = db.query(ChatLog).filter(ChatLog.is_answered == 1).count()
    unanswered_count = db.query(ChatLog).filter(ChatLog.is_answered == 0).count()
    like_count = db.query(ChatLog).filter(ChatLog.feedback == 1).count()
    dislike_count = db.query(ChatLog).filter(ChatLog.feedback == 2).count()

    return APIResponse(code=0, message="success", data={
        "user_count": user_count,
        "session_count": session_count,
        "message_count": message_count,
        "total_queries": log_count,
        "answered_queries": answered_count,
        "unanswered_queries": unanswered_count,
        "answer_rate": round(answered_count / log_count * 100, 1) if log_count > 0 else 0,
        "like_count": like_count,
        "dislike_count": dislike_count,
        "satisfaction_rate": round(like_count / (like_count + dislike_count) * 100, 1) if (like_count + dislike_count) > 0 else 0,
    })


# ==================== 部门管理 ====================

# 公开接口：部门列表（注册页使用，无需登录）
@router.get("/departments/public", response_model=APIResponse, summary="公开部门列表")
def list_departments_public(
    db: Session = Depends(get_db),
):
    """获取部门名称列表（无需登录，供注册页使用）"""
    depts = db.query(Department).order_by(Department.sort_order).all()
    data = [{"id": d.id, "name": d.name} for d in depts]
    return APIResponse(code=0, message="success", data=data)


@router.get("/departments", response_model=APIResponse, summary="部门列表")
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取部门列表（含成员数量统计）"""
    depts = db.query(Department).order_by(Department.sort_order).all()
    data = []
    for d in depts:
        member_count = db.query(User).filter(
            User.dept_id == d.id, User.status == 1
        ).count()
        manager_name = None
        if d.manager_id:
            mgr = db.query(User).filter(User.id == d.manager_id).first()
            manager_name = mgr.real_name if mgr else None
        data.append({
            "id": d.id, "name": d.name,
            "parent_id": d.parent_id, "sort_order": d.sort_order,
            "description": d.description,
            "manager_id": d.manager_id, "manager_name": manager_name,
            "member_count": member_count,
            "created_at": str(d.created_at),
        })
    return APIResponse(code=0, message="success", data=data)


@router.post("/departments", response_model=APIResponse, summary="创建部门")
def create_department(
    name: str = Query(..., description="部门名称"),
    description: Optional[str] = Query(default=None, description="部门描述"),
    parent_id: int = Query(default=0, description="上级部门ID"),
    manager_id: Optional[int] = Query(default=None, description="负责人ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """创建新部门"""
    existing = db.query(Department).filter(Department.name == name).first()
    if existing:
        return APIResponse(code=3001, message="部门名称已存在")
    dept = Department(
        name=name, description=description,
        parent_id=parent_id, manager_id=manager_id,
        sort_order=db.query(Department).count() + 1,
    )
    db.add(dept)
    db.flush()
    db.refresh(dept)
    return APIResponse(code=0, message="部门创建成功", data={"id": dept.id, "name": dept.name})


@router.put("/departments/{dept_id}", response_model=APIResponse, summary="更新部门")
def update_department(
    dept_id: int,
    name: Optional[str] = Query(default=None, description="部门名称"),
    description: Optional[str] = Query(default=None, description="部门描述"),
    manager_id: Optional[int] = Query(default=None, description="负责人ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """更新部门信息"""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        return APIResponse(code=3001, message="部门不存在")
    if name is not None:
        dept.name = name
    if description is not None:
        dept.description = description
    if manager_id is not None:
        dept.manager_id = manager_id
    db.flush()
    return APIResponse(code=0, message="部门更新成功")


@router.delete("/departments/{dept_id}", response_model=APIResponse, summary="删除部门")
def delete_department(
    dept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """删除部门（仅当无成员时）"""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        return APIResponse(code=3001, message="部门不存在")
    member_count = db.query(User).filter(
        User.dept_id == dept.id, User.status == 1
    ).count()
    if member_count > 0:
        return APIResponse(code=3002, message=f"该部门还有 {member_count} 名成员，无法删除")
    db.delete(dept)
    db.flush()
    return APIResponse(code=0, message="部门已删除")


# ==================== 增强版统计概览（含部门维度） ====================

@router.get("/stats/departments", response_model=APIResponse, summary="部门统计")
def get_dept_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """按部门统计问答数据"""
    depts = db.query(Department).order_by(Department.sort_order).all()
    data = []
    for d in depts:
        dept_users = db.query(User.id).filter(
            User.dept_id == d.id, User.status == 1
        ).subquery()
        query_count = db.query(ChatLog).filter(
            ChatLog.user_id.in_(dept_users)
        ).count()
        member_count = db.query(User).filter(
            User.dept_id == d.id, User.status == 1
        ).count()
        data.append({
            "department_name": d.name,
            "member_count": member_count,
            "query_count": query_count,
            "avg_per_user": round(query_count / member_count, 1) if member_count > 0 else 0,
        })
    return APIResponse(code=0, message="success", data=data)


# ==================== 数据导出 ====================

import csv
import io


def _csv_safe(value) -> str:
    """CSV 防公式注入：以 = + - @ 开头的单元格加单引号前缀，Excel 中按文本处理"""
    s = "" if value is None else str(value)
    if s.startswith(("=", "+", "-", "@")):
        return "'" + s
    return s


@router.get("/export/logs", summary="导出问答日志 CSV")
def export_chat_logs(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """导出问答日志为 CSV 文件"""
    query = db.query(ChatLog)
    if date_from:
        query = query.filter(ChatLog.created_at >= f"{date_from}T00:00:00")
    if date_to:
        query = query.filter(ChatLog.created_at <= f"{date_to}T23:59:59")
    logs = query.order_by(ChatLog.created_at.desc()).limit(5000).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "会话ID", "用户ID", "问题", "答案", "是否命中",
                      "反馈(0=无/1=赞/2=踩)", "检索耗时ms", "LLM耗时ms", "总耗时ms", "时间"])
    for log in logs:
        writer.writerow([
            _csv_safe(log.id), _csv_safe(log.session_id), _csv_safe(log.user_id),
            _csv_safe(log.question), _csv_safe((log.answer or "")[:500]),
            _csv_safe(log.is_answered), _csv_safe(log.feedback),
            _csv_safe(log.retrieval_ms), _csv_safe(log.llm_ms), _csv_safe(log.total_ms),
            _csv_safe(str(log.created_at)),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=chat_logs.csv"},
    )


# ==================== 公告管理 ====================

@router.get("/announcements/active", response_model=APIResponse, summary="获取有效公告（公开）")
def get_active_announcements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取当前有效的公告（所有登录用户可访问）"""
    from datetime import datetime
    now = datetime.now()
    items = db.query(Announcement).filter(
        Announcement.is_published == True,
        (Announcement.expire_at == None) | (Announcement.expire_at > now),
    ).order_by(Announcement.publish_at.desc()).limit(5).all()
    data = [{
        "id": a.id, "title": a.title, "content": a.content,
        "publish_at": str(a.publish_at) if a.publish_at else None,
    } for a in items]
    return APIResponse(code=0, message="success", data=data)


@router.get("/announcements", response_model=APIResponse, summary="公告列表")
def list_announcements(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """获取公告列表（管理端）"""
    query = db.query(Announcement).order_by(Announcement.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    data = [{
        "id": a.id, "title": a.title, "content": a.content,
        "is_published": a.is_published,
        "created_at": str(a.created_at),
        "publish_at": str(a.publish_at) if a.publish_at else None,
        "expire_at": str(a.expire_at) if a.expire_at else None,
    } for a in items]
    return APIResponse(
        code=0, message="success",
        data=PaginatedData.from_query(data, total, page, page_size).model_dump()
    )


@router.post("/announcements", response_model=APIResponse, summary="创建公告")
def create_announcement(
    title: str = Query(..., description="公告标题"),
    content: str = Query(..., description="公告内容（支持 Markdown）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """创建新公告"""
    ann = Announcement(
        title=title, content=content,
        created_by=current_user.id,
    )
    db.add(ann)
    db.flush()
    db.refresh(ann)
    return APIResponse(code=0, message="公告创建成功", data={"id": ann.id})


@router.put("/announcements/{ann_id}", response_model=APIResponse, summary="更新公告")
def update_announcement(
    ann_id: int,
    title: Optional[str] = Query(default=None),
    content: Optional[str] = Query(default=None),
    is_published: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """更新公告"""
    ann = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not ann:
        return APIResponse(code=3001, message="公告不存在")
    if title is not None:
        ann.title = title
    if content is not None:
        ann.content = content
    if is_published is not None:
        ann.is_published = is_published
    db.flush()
    return APIResponse(code=0, message="公告更新成功")


@router.delete("/announcements/{ann_id}", response_model=APIResponse, summary="删除公告")
def delete_announcement(
    ann_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """删除公告"""
    ann = db.query(Announcement).filter(Announcement.id == ann_id).first()
    if not ann:
        return APIResponse(code=3001, message="公告不存在")
    db.delete(ann)
    db.flush()
    return APIResponse(code=0, message="公告已删除")
