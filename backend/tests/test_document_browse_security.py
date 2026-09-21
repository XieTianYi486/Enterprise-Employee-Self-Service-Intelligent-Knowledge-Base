# ============================================================
# P0 安全修复测试：文档浏览链路密级过滤
# 覆盖 DocumentService.get_documents(max_security_level) 与
# get_visible_document 的可见性判定（列表/详情/原文接口共用）
# ============================================================

import pytest

from app.core.exceptions import NotFoundException
from app.models.document import Document
from app.services.document_service import DocumentService


def _make_doc(db, title, security_level=1, status=1, review_status=2):
    """创建文档记录（仅 flush，不 commit，测试结束由 db fixture 回滚）"""
    doc = Document(
        title=title,
        file_name=f"{title}.md",
        file_path=f"/tmp/{title}.md",
        file_size=100,
        file_type="md",
        security_level=security_level,
        status=status,
        review_status=review_status,
    )
    db.add(doc)
    db.flush()
    db.refresh(doc)
    return doc


class TestListFilterByMaxSecurityLevel:
    """列表查询：密级上限过滤（security_level <= 上限）"""

    def test_employee_cannot_see_higher_level_docs(self, db):
        visible = _make_doc(db, "公开制度_可见", security_level=1)
        hidden = _make_doc(db, "机密制度_不可见", security_level=3)

        items, total = DocumentService.get_documents(
            db, page=1, page_size=20,
            published_only=True, max_security_level=1,
        )
        titles = [d.title for d in items]
        assert visible.title in titles
        assert hidden.title not in titles
        # 上限语义是 <= 而非 ==：密级 1 的用户看不到密级 3
        assert total >= 1

    def test_dept_admin_sees_up_to_level3_but_not_level4(self, db):
        level3 = _make_doc(db, "机密制度_三级", security_level=3)
        level4 = _make_doc(db, "绝密制度_四级", security_level=4)

        items, _ = DocumentService.get_documents(
            db, page=1, page_size=20,
            published_only=True, max_security_level=3,
        )
        titles = [d.title for d in items]
        assert level3.title in titles
        assert level4.title not in titles

    def test_no_max_level_means_no_filter(self, db):
        doc = _make_doc(db, "绝密制度_不过滤", security_level=4)

        items, _ = DocumentService.get_documents(db, page=1, page_size=20)
        titles = [d.title for d in items]
        assert doc.title in titles


class TestGetVisibleDocument:
    """单文档可见性判定（详情/原文/版本接口共用）"""

    def test_blocks_doc_above_user_level(self, db):
        doc = _make_doc(db, "绝密制度_越权", security_level=4)
        with pytest.raises(NotFoundException):
            DocumentService.get_visible_document(
                db, doc.id, max_security_level=1, published_only=True,
            )

    def test_blocks_unpublished_doc(self, db):
        doc = _make_doc(db, "草稿文档_未发布", status=0, review_status=0)
        with pytest.raises(NotFoundException):
            DocumentService.get_visible_document(
                db, doc.id, max_security_level=4, published_only=True,
            )

    def test_blocks_pending_review_doc(self, db):
        doc = _make_doc(db, "待审核文档", status=0, review_status=1)
        with pytest.raises(NotFoundException):
            DocumentService.get_visible_document(
                db, doc.id, max_security_level=4, published_only=True,
            )

    def test_allows_doc_within_user_level(self, db):
        doc = _make_doc(db, "公开制度_正常", security_level=1)
        got = DocumentService.get_visible_document(
            db, doc.id, max_security_level=1, published_only=True,
        )
        assert got.id == doc.id

    def test_admin_unrestricted(self, db):
        doc = _make_doc(db, "绝密制度_管理员可见", security_level=4, status=0)
        # 不传 max_security_level / published_only = 管理员不受限制
        got = DocumentService.get_visible_document(db, doc.id)
        assert got.id == doc.id

    def test_missing_doc_raises(self, db):
        with pytest.raises(NotFoundException):
            DocumentService.get_visible_document(db, 999999, max_security_level=1)
