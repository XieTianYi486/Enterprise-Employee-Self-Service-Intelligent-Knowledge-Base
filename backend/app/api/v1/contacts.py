# ============================================================
# 通讯录接口
# 部门组织树 + 成员信息（全体登录用户可查）
# ============================================================

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.db.sqlite import get_db
from app.api.deps import get_current_active_user
from app.models.user import User, Department
from app.schemas.common import APIResponse

router = APIRouter(tags=["通讯录"])


@router.get("/contacts/tree", response_model=APIResponse, summary="通讯录组织树")
def get_contacts_tree(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    通讯录：部门树 + 各部门成员（脱敏字段）。
    所有登录用户可查，用于员工互相了解组织架构与联系方式。
    """
    depts = db.query(Department).order_by(Department.sort_order, Department.id).all()
    users = (
        db.query(User)
        .options(joinedload(User.role))
        .filter(User.status == 1)
        .all()
    )

    dept_map = {d.id: {
        "id": d.id,
        "name": d.name,
        "parent_id": d.parent_id,
        "sort_order": d.sort_order,
        "manager_id": d.manager_id,
        "members": [],
    } for d in depts}
    unassigned = []

    for u in users:
        member = {
            "id": u.id,
            "real_name": u.real_name or u.username,
            "username": u.username,
            "position": u.position,
            "email": u.email,
            "phone": u.phone,
            "avatar_url": u.avatar_url,
            "role_name": u.role.name if u.role else None,
            "entry_date": str(u.entry_date) if u.entry_date else None,
        }
        if u.dept_id and u.dept_id in dept_map:
            dept_map[u.dept_id]["members"].append(member)
        else:
            unassigned.append(member)

    # 组装树（parent_id 0 为顶级）
    top_level = []
    for d in dept_map.values():
        if d["parent_id"] and d["parent_id"] in dept_map:
            parent = dept_map[d["parent_id"]]
            parent.setdefault("children", []).append(d)
        else:
            top_level.append(d)

    return APIResponse(code=0, message="success", data={
        "tree": top_level,
        "unassigned": unassigned,
    })
