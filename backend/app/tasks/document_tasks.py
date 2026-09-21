# ============================================================
# 文档异步处理任务
# 使用 threading 实现后台处理（替代 Celery）
# ============================================================

import logging
import sys
import threading
import traceback
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.sqlite import SessionLocal
from app.models.document import Document, DocChunk
from app.rag.ingestion import process_document, remove_document_from_index

# Windows 控制台 GBK 编码兼容
# pytest 运行时跳过：重包装 stdout/stderr 会破坏 pytest 的捕获流
# （导致 "I/O operation on closed file" 并掩盖真实测试错误）
if sys.platform == "win32" and "pytest" not in sys.modules:
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass  # 非标准流（如重定向）时保持原样，避免影响主流程

logger = logging.getLogger(__name__)


def process_document_async(document_id: int) -> None:
    """
    异步处理文档（在后台线程中执行）

    流程：
    1. 从数据库读取文档信息
    2. 调用 Ingestion 流水线
    3. 更新数据库状态和分块记录
    4. 处理失败时更新为失败状态

    参数:
        document_id: 文档数据库 ID
    """
    thread = threading.Thread(
        target=_process_document_task,
        args=(document_id,),
        daemon=True,
        name=f"doc-process-{document_id}",
    )
    thread.start()


def _process_document_task(document_id: int) -> None:
    """后台线程执行的实际处理逻辑"""
    db = SessionLocal()

    try:
        # 获取文档记录
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.info(f"[任务] 文档 {document_id} 不存在")
            return

        # 更新状态为"处理中"
        doc.status = 0
        db.commit()

        logger.info(f"[任务] 开始处理文档: {doc.title} ({doc.file_type})")

        # 调用 Ingestion 流水线（项目目录搬迁后旧绝对路径可能失效，按当前上传目录兜底解析）
        from app.services.document_service import DocumentService
        file_path = str(DocumentService.resolve_file_path(doc.file_path))
        chunk_count, chunk_ids, chunk_records = process_document(
            file_path=file_path,
            file_type=doc.file_type,
            document_id=doc.id,
            title=doc.title,
            category_id=doc.category_id,
            security_level=doc.security_level,
        )

        # 保存分块记录到数据库（含完整内容）
        for i, chunk_id in enumerate(chunk_ids):
            chunk_info = chunk_records[i] if i < len(chunk_records) else {}
            chunk_record = DocChunk(
                document_id=doc.id,
                chunk_index=i,
                content=chunk_info.get("content", ""),
                chapter=chunk_info.get("chapter", ""),
                page_start=chunk_info.get("page", 1),
                chroma_id=chunk_id,
                token_count=chunk_info.get("token_count", 0),
            )
            db.add(chunk_record)

        # 更新文档状态
        doc.status = 1  # 已发布
        doc.chunk_count = chunk_count
        db.commit()

        logger.info(f"[任务] 文档处理完成: {doc.title}, 共 {chunk_count} 个分块")

    except Exception as e:
        # 处理失败
        db.rollback()
        try:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = 3  # 处理失败
                db.commit()
        except Exception:
            pass

        traceback.print_exc()
        logger.info(f"[任务] 文档处理失败: {document_id}, 错误: {str(e)}")

    finally:
        db.close()


def reindex_document_async(document_id: int) -> None:
    """
    重新索引文档（先删除旧数据，再重新处理）
    """
    # 先删除旧索引
    removed = remove_document_from_index(document_id)
    logger.info(f"[任务] 已删除文档 {document_id} 的 {removed} 个旧分块")

    # 清除数据库中的旧分块记录
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            db.query(DocChunk).filter(DocChunk.document_id == document_id).delete()
            doc.chunk_count = 0
            doc.status = 0
            db.commit()
    except Exception as e:
        db.rollback()
        logger.info(f"[任务] 清除旧分块失败: {e}")
    finally:
        db.close()

    # 重新处理
    process_document_async(document_id)
