# ============================================================
# SQLAlchemy 数据模型 - 文档管理
# 支持分类树、版本管理、标签、密级
# 旧项目仅有简单的知识文档表，无版本和分类
# ============================================================

from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Column, Integer, Integer, String, Text,
    DateTime, Date, JSON, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.sqlite import Base
from app.models.user import utcnow


class Category(Base):
    """
    文档分类表（多级分类树）
    通过 parent_id 自引用实现树形结构
    """
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="分类名称"
    )
    parent_id: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="父分类ID（0=根节点）"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="排序号"
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="分类描述"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    # 关系
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="category"
    )

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"


class Document(Base):
    """
    文档表
    核心字段：版本管理、密级、分类、标签
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="文档标题"
    )
    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="原始文件名"
    )
    file_path: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="本地存储路径"
    )
    file_size: Mapped[int] = mapped_column(
        Integer, default=0, comment="文件大小（字节）"
    )
    file_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="文件类型：pdf/docx/xlsx/md/txt"
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True, comment="分类ID"
    )
    version: Mapped[str] = mapped_column(
        String(32), default="1.0", nullable=False, comment="版本号"
    )
    security_level: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False,
        comment="密级：1=公开, 2=内部, 3=机密, 4=绝密"
    )
    status: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="状态：0=处理中, 1=已发布, 2=已归档, 3=处理失败"
    )
    # ===== 知识审核发布流字段 =====
    # 文档上传入库后置于"待审核"，仅"已通过"的文档才对普通员工可见/可检索
    review_status: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, index=True,
        comment="审核状态：0=草稿, 1=待审核, 2=已通过, 3=已驳回"
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="审核人ID"
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="审核时间"
    )
    review_comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="审核意见"
    )
    publish_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="发布日期"
    )
    expire_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, comment="失效日期（NULL=永久有效）"
    )
    tags: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="标签列表（JSON 数组）"
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="分块数量"
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="上传人ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    # 关系
    category: Mapped[Optional["Category"]] = relationship(
        "Category", back_populates="documents"
    )
    chunks: Mapped[list["DocChunk"]] = relationship(
        "DocChunk", back_populates="document", cascade="all, delete-orphan"
    )
    versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Document(id={self.id}, title='{self.title}')>"


class DocumentVersion(Base):
    """
    文档版本记录表
    文档更新时旧版本自动归档到此
    """
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="文档ID"
    )
    version: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="版本号"
    )
    file_path: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="归档文件路径"
    )
    file_size: Mapped[int] = mapped_column(
        Integer, default=0, comment="文件大小"
    )
    changelog: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="变更说明"
    )
    archived_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    # 关系
    document: Mapped["Document"] = relationship(
        "Document", back_populates="versions"
    )

    def __repr__(self):
        return f"<DocumentVersion(document_id={self.document_id}, v={self.version})>"


class DocChunk(Base):
    """
    文档分块表
    记录每个分块的文本内容、章节、页码信息
    """
    __tablename__ = "doc_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="所属文档ID"
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="分块序号"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="分块文本内容"
    )
    chapter: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="所属章节"
    )
    page_start: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="起始页码"
    )
    page_end: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="结束页码"
    )
    token_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="估算 token 数量"
    )
    chroma_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True, comment="ChromaDB 中对应的向量 ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    # 关系
    document: Mapped["Document"] = relationship(
        "Document", back_populates="chunks"
    )

    def __repr__(self):
        return f"<DocChunk(id={self.id}, doc_id={self.document_id}, idx={self.chunk_index})>"
