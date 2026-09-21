# ============================================================
# 检索可见性单元测试：发布状态 + 审核状态 + 密级三重过滤
# 验证问答只引用"已发布 + 已通过审核 + 密级内"的文档
# ============================================================

from app.models.document import Document
from app.services.chat_service import ChatService


def _make_doc(db, title, security_level, status, review_status):
    doc = Document(
        title=title,
        file_name=f"{title}.md",
        file_path=f"/tmp/{title}.md",
        file_type="md",
        security_level=security_level,
        status=status,
        review_status=review_status,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def test_visible_doc_ids_filters(db):
    """普通员工仅见公开已发布已通过文档；未发布/待审核对任何人不可见"""
    published_public = _make_doc(db, "公开制度", 1, 1, 2)
    published_secret = _make_doc(db, "机密制度", 3, 1, 2)
    _make_doc(db, "待审核文档", 1, 1, 1)
    _make_doc(db, "未发布文档", 1, 0, 2)

    # 普通员工（密级上限 1）
    assert ChatService._visible_doc_ids(1) == {published_public.id}
    # 管理员（密级上限 4）：机密文档可见，但未发布/待审核仍不可见
    assert ChatService._visible_doc_ids(4) == {
        published_public.id, published_secret.id,
    }
