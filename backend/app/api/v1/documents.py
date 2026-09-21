# ============================================================
# 文档管理接口
# CRUD + 版本管理 + 分类管理 + 审核发布
# ============================================================

import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, Query
from sqlalchemy.orm import Session

from app.db.sqlite import get_db
from app.api.deps import (
    require_knowledge_admin, require_permission, get_security_level,
)
from app.models.user import User
from app.models.document import Document, Category
from app.schemas.common import APIResponse, PaginatedData
from app.schemas.document import (
    DocumentResponse, DocumentUpdate, DocumentVersionResponse,
    DocumentStatsResponse, CategoryCreate, CategoryUpdate, CategoryResponse,
)
from app.services.document_service import DocumentService
from app.services.audit_service import add_audit_log

router = APIRouter(prefix="/documents", tags=["文档管理"])


# ==================== 浏览可见性辅助 ====================

def _is_admin_user(user: User) -> bool:
    """管理员（超管/知识库管理员）浏览文档不受密级与发布状态限制"""
    role_code = user.role.code if user.role else "employee"
    return role_code in ("super_admin", "knowledge_admin")


def _get_visible_document(db: Session, doc_id: int, user: User) -> Document:
    """
    获取对当前用户可见的文档。

    管理员不受限制；普通用户要求：已发布 + 已通过审核 + 密级 <= 用户密级。
    不满足时统一按"不存在"处理，避免向无权用户泄露文档存在性。
    """
    if _is_admin_user(user):
        return DocumentService.get_document(db, doc_id)
    role_code = user.role.code if user.role else "employee"
    return DocumentService.get_visible_document(
        db, doc_id,
        max_security_level=get_security_level(role_code),
        published_only=True,
    )


# ==================== 文档 CRUD ====================

@router.post("/upload", response_model=APIResponse, summary="上传文档")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    category_id: Optional[int] = Form(default=None),
    tags: Optional[str] = Form(default=None),
    review_mode: Optional[str] = Form(default="pending"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """
    上传文档文件
    支持 PDF / DOCX / XLSX / MD / TXT 格式

    review_mode: pending=提交审核（默认）, draft=保存草稿
    """
    import json
    tag_list = json.loads(tags) if tags else []

    doc = DocumentService.create_document(
        db=db,
        file=file.file,
        filename=file.filename,
        title=title,
        category_id=category_id,
        tags=tag_list,
        user_id=current_user.id,
    )
    # 上传审核策略：draft 保存为草稿，其余进入待审核
    if review_mode == "draft":
        doc.review_status = 0
        db.flush()

    # 使用 FastAPI BackgroundTasks 确保在响应提交后再启动后台处理
    from app.tasks.document_tasks import process_document_async
    background_tasks.add_task(process_document_async, doc.id)

    return APIResponse(
        code=0,
        message="文档上传成功，正在处理中...",
        data={"document_id": doc.id, "status": doc.status}
    )


@router.get("", response_model=APIResponse, summary="文档列表")
def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    file_type: Optional[str] = None,
    status: Optional[int] = None,
    review_status: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents:read")),
):
    """获取文档列表（分页 + 筛选，需 documents:read 权限）"""
    # 普通员工仅可见"已发布 + 已通过审核 + 密级内"的文档，防止未审核/越权内容泄露
    is_admin = _is_admin_user(current_user)
    published_only = not is_admin
    max_level = None if is_admin else get_security_level(
        current_user.role.code if current_user.role else "employee"
    )

    items, total = DocumentService.get_documents(
        db, page, page_size, keyword, category_id,
        file_type, status, review_status=review_status,
        published_only=published_only,
        max_security_level=max_level,
    )

    # 转为响应模型
    doc_list = []
    for doc in items:
        cat_name = doc.category.name if doc.category else None
        doc_list.append(DocumentResponse(
            id=doc.id, title=doc.title, file_name=doc.file_name,
            file_size=doc.file_size, file_type=doc.file_type,
            category_id=doc.category_id, category_name=cat_name,
            version=doc.version, security_level=doc.security_level,
            status=doc.status, review_status=doc.review_status,
            review_comment=doc.review_comment, reviewed_at=doc.reviewed_at,
            publish_date=doc.publish_date,
            expire_date=doc.expire_date, tags=doc.tags,
            chunk_count=doc.chunk_count, created_by=doc.created_by,
            created_at=doc.created_at, updated_at=doc.updated_at,
        ).model_dump())

    return APIResponse(
        code=0,
        message="success",
        data=PaginatedData.from_query(doc_list, total, page, page_size).model_dump()
    )


@router.get("/{doc_id}", response_model=APIResponse, summary="文档详情")
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents:read")),
):
    """获取单个文档详情（需 documents:read 权限；普通用户仅可见已发布且密级内的文档）"""
    doc = _get_visible_document(db, doc_id, current_user)
    cat_name = doc.category.name if doc.category else None
    return APIResponse(
        code=0,
        message="success",
        data=DocumentResponse(
            id=doc.id, title=doc.title, file_name=doc.file_name,
            file_size=doc.file_size, file_type=doc.file_type,
            category_id=doc.category_id, category_name=cat_name,
            version=doc.version, security_level=doc.security_level,
            status=doc.status, review_status=doc.review_status,
            review_comment=doc.review_comment, reviewed_at=doc.reviewed_at,
            publish_date=doc.publish_date,
            expire_date=doc.expire_date, tags=doc.tags,
            chunk_count=doc.chunk_count, created_by=doc.created_by,
            created_at=doc.created_at, updated_at=doc.updated_at,
        ).model_dump()
    )


@router.put("/{doc_id}", response_model=APIResponse, summary="更新文档元数据")
def update_document(
    doc_id: int,
    data: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """更新文档的元数据（标题、分类、密级、标签等）"""
    doc = DocumentService.update_document(db, doc_id, data)
    return APIResponse(code=0, message="更新成功", data={"document_id": doc.id})


@router.delete("/{doc_id}", response_model=APIResponse, summary="删除文档")
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """删除文档及其所有关联数据（分块、版本、向量）"""
    DocumentService.delete_document(db, doc_id)
    return APIResponse(code=0, message="文档已删除")


@router.post("/{doc_id}/reindex", response_model=APIResponse, summary="重新索引文档")
def reindex_document(
    doc_id: int,
    current_user: User = Depends(require_knowledge_admin),
):
    """重新对文档进行分块、向量化和索引"""
    DocumentService.reindex_document(doc_id)
    return APIResponse(code=0, message="文档重新索引任务已启动")


@router.post("/{doc_id}/upload-version", response_model=APIResponse, summary="上传新版本")
async def upload_new_version(
    doc_id: int,
    file: UploadFile = File(...),
    changelog: Optional[str] = Form(default=None),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """
    上传文档的新版本

    流程：
    1. 归档当前版本
    2. 上传新文件
    3. 重新索引
    """
    doc = DocumentService.upload_new_version(
        db=db,
        doc_id=doc_id,
        file=file.file,
        filename=file.filename,
        changelog=changelog,
        user_id=current_user.id,
    )

    from app.tasks.document_tasks import process_document_async
    background_tasks.add_task(process_document_async, doc.id)

    return APIResponse(
        code=0,
        message="新版本上传成功，正在重新索引...",
        data={
            "document_id": doc.id,
            "version": doc.version,
            "status": doc.status,
        }
    )


# ==================== 文档版本 ====================

@router.get("/{doc_id}/versions", response_model=APIResponse, summary="文档版本列表")
def get_document_versions(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents:read")),
):
    """获取文档的所有历史版本（需 documents:read 权限；普通用户仅可见密级内的文档）"""
    doc = _get_visible_document(db, doc_id, current_user)
    versions = [
        DocumentVersionResponse(
            id=v.id, document_id=v.document_id, version=v.version,
            file_size=v.file_size, changelog=v.changelog, archived_at=v.archived_at
        ).model_dump()
        for v in doc.versions
    ]
    return APIResponse(code=0, message="success", data=versions)


# ==================== 文档分类 ====================

@router.get("/categories/tree", response_model=APIResponse, summary="分类树")
def get_category_tree(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents:read")),
):
    """
    获取文档分类树（多级嵌套结构）

    普通用户的 document_count 仅统计其可见文档（已发布 + 已过审 + 密级内），
    管理员统计全部文档。
    """
    categories = db.query(Category).order_by(Category.sort_order).all()
    if _is_admin_user(current_user):
        visible_doc_ids = None
    else:
        role_code = current_user.role.code if current_user.role else "employee"
        visible_doc_ids = {
            r[0] for r in db.query(Document.id).filter(
                Document.status == 1,
                Document.review_status == 2,
                Document.security_level <= get_security_level(role_code),
            ).all()
        }
    tree = _build_category_tree(categories, visible_doc_ids=visible_doc_ids)
    return APIResponse(code=0, message="success", data=tree)


def _build_category_tree(
    categories: list[Category],
    parent_id: int = 0,
    visible_doc_ids: Optional[set] = None,
) -> list[dict]:
    """递归构建分类树；visible_doc_ids 为 None 时统计全部文档（管理员）"""
    result = []
    for cat in categories:
        if cat.parent_id == parent_id:
            children = _build_category_tree(categories, cat.id, visible_doc_ids)
            if visible_doc_ids is None:
                doc_count = len(cat.documents)
            else:
                doc_count = sum(1 for d in cat.documents if d.id in visible_doc_ids)
            result.append({
                "id": cat.id,
                "name": cat.name,
                "parent_id": cat.parent_id,
                "sort_order": cat.sort_order,
                "description": cat.description,
                "document_count": doc_count,
                "children": children,
            })
    return result


@router.post("/categories", response_model=APIResponse, summary="创建分类")
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """创建文档分类"""
    cat = Category(**data.model_dump())
    db.add(cat)
    db.flush()
    db.refresh(cat)
    return APIResponse(code=0, message="分类创建成功", data={"id": cat.id})


@router.put("/categories/{cat_id}", response_model=APIResponse, summary="更新分类")
def update_category(
    cat_id: int,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """更新文档分类"""
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat:
        return APIResponse(code=3001, message="分类不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(cat, k, v)
    db.flush()
    return APIResponse(code=0, message="分类更新成功")


@router.delete("/categories/{cat_id}", response_model=APIResponse, summary="删除分类")
def delete_category(
    cat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """删除分类（如果分类下有文档则无法删除）"""
    cat = db.query(Category).filter(Category.id == cat_id).first()
    if not cat:
        return APIResponse(code=3001, message="分类不存在")
    if len(cat.documents) > 0:
        return APIResponse(code=3002, message="该分类下还有文档，无法删除")
    db.delete(cat)
    db.flush()
    return APIResponse(code=0, message="分类已删除")


# ==================== 文档统计 ====================

@router.get("/stats/overview", response_model=APIResponse, summary="文档统计概览")
def get_document_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """获取文档统计概览数据（仅知识库管理员，统计含全部密级/状态）"""
    stats = DocumentService.get_stats(db)
    return APIResponse(code=0, message="success", data=stats)


# ==================== 文档内容查看 ====================

@router.get("/{doc_id}/content", response_model=APIResponse, summary="查看文档内容")
def get_document_content(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("documents:read")),
):
    """
    获取文档的原始文本内容（Markdown 渲染用）
    用于前端查看文档原文
    """
    doc = _get_visible_document(db, doc_id, current_user)

    # 读取文件内容：文本格式直接读取，二进制格式调用解析器
    from app.rag.ingestion import DocumentParser

    # 项目目录搬迁后 DB 中的旧绝对路径可能失效，按当前上传目录兜底解析
    file_path = str(DocumentService.resolve_file_path(doc.file_path))
    if not os.path.exists(file_path):
        return APIResponse(code=3003, message="文档文件不存在")

    text_types = {"md", "txt"}
    if doc.file_type in text_types:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        # PDF/Word/Excel 等二进制格式，调用解析器提取文本
        try:
            content, _ = DocumentParser.parse(file_path, doc.file_type)
        except Exception:
            return APIResponse(code=3004, message="文档内容解析失败，请检查文件是否损坏")

    return APIResponse(
        code=0,
        message="success",
        data={
            "document_id": doc.id,
            "title": doc.title,
            "file_type": doc.file_type,
            "content": content,
            "file_size": doc.file_size,
        }
    )


# ==================== 知识审核发布流 ====================

admin_review_router = APIRouter(
    prefix="/admin/documents", tags=["知识审核"]
)


@admin_review_router.get("/review-queue", response_model=APIResponse, summary="待审核文档列表")
def get_review_queue(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    review_status: Optional[int] = Query(default=1, description="0草稿/1待审核/2已通过/3已驳回"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """获取指定审核状态的文档列表（审核工作台）"""
    items, total = DocumentService.get_documents(
        db, page=page, page_size=page_size,
        review_status=review_status,
    )
    doc_list = []
    for doc in items:
        cat_name = doc.category.name if doc.category else None
        doc_list.append(DocumentResponse(
            id=doc.id, title=doc.title, file_name=doc.file_name,
            file_size=doc.file_size, file_type=doc.file_type,
            category_id=doc.category_id, category_name=cat_name,
            version=doc.version, security_level=doc.security_level,
            status=doc.status, review_status=doc.review_status,
            review_comment=doc.review_comment, reviewed_at=doc.reviewed_at,
            publish_date=doc.publish_date,
            expire_date=doc.expire_date, tags=doc.tags,
            chunk_count=doc.chunk_count, created_by=doc.created_by,
            created_at=doc.created_at, updated_at=doc.updated_at,
        ).model_dump())
    return APIResponse(
        code=0, message="success",
        data=PaginatedData.from_query(doc_list, total, page, page_size).model_dump()
    )


@admin_review_router.post("/{doc_id}/review", response_model=APIResponse, summary="文档审核")
def review_document(
    doc_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """
    审核文档：
      - action=approve : 通过并发布
      - action=reject  : 驳回（comment 可填驳回意见）
      - action=submit  : 提交审核（草稿/驳回 -> 待审核）
      - action=recall  : 撤回（待审核 -> 草稿）
    body: {"action": "...", "comment": "可选", "ids": [...]}
    """
    action = body.get("action")
    comment = (body.get("comment") or "").strip() or None
    if action not in ("approve", "reject", "submit", "recall"):
        return APIResponse(code=1001, message="action 仅支持 approve / reject / submit / recall")
    doc = DocumentService.review_document(
        db, doc_id, action,
        reviewer_id=current_user.id,
        comment=comment,
    )
    add_audit_log(
        db=db, module="document", action=f"review_{action}",
        status="success",
        user_id=current_user.id, username=current_user.username,
        target_type="document", target_id=str(doc.id),
        detail={"title": doc.title, "comment": comment},
    )
    msg = {
        "approve": "审核通过，文档已发布",
        "reject": "已驳回该文档",
        "submit": "已重新提交审核",
        "recall": "已撤回为草稿",
    }[action]
    return APIResponse(
        code=0,
        message=msg,
        data={
            "document_id": doc.id,
            "review_status": doc.review_status,
            "status": doc.status,
        }
    )


@admin_review_router.post("/batch-review", response_model=APIResponse, summary="批量审核")
def batch_review_document(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_knowledge_admin),
):
    """
    批量审核：body = {"action": "approve|reject", "ids": [1,2,3], "comment": "可选"}
    批量场景仅支持 approve / reject。
    """
    action = body.get("action")
    ids = body.get("ids") or []
    comment = (body.get("comment") or "").strip() or None
    if action not in ("approve", "reject"):
        return APIResponse(code=1001, message="批量仅支持 approve / reject")
    if not ids or not isinstance(ids, list):
        return APIResponse(code=1001, message="请提供要审核的文档 ids")
    success = 0
    for doc_id in ids:
        try:
            doc = DocumentService.review_document(
                db, doc_id, action, reviewer_id=current_user.id, comment=comment,
            )
            add_audit_log(
                db=db, module="document", action=f"review_{action}",
                status="success",
                user_id=current_user.id, username=current_user.username,
                target_type="document", target_id=str(doc.id),
                detail={"title": doc.title},
            )
            success += 1
        except Exception:
            continue
    verb = "通过" if action == "approve" else "驳回"
    return APIResponse(
        code=0,
        message=f"批量{verb}完成：成功 {success} 条",
        data={"success": success},
    )
