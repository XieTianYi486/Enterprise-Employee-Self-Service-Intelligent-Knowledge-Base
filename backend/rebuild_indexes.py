# -*- coding: utf-8 -*-
"""
索引重建脚本
从数据库 DocChunk 表全量重建 FAISS 向量索引 + BM25 关键词索引
用于修复索引与数据库不一致（残留脏数据）的场景

用法: python rebuild_indexes.py
"""
import os
import sys
import time

import sys as _sys
if _sys.platform == "win32":
    import io
    _sys.stdout = io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.core.config import settings
from app.db.sqlite import SessionLocal
from app.models.document import Document, DocChunk
from app.rag.embeddings.dashscope_embeddings import get_embeddings
from app.rag.retrievers.bm25_retriever import BM25Retriever, BM25_INDEX_PATH


def main():
    print("=" * 60)
    print("重建 FAISS + BM25 索引")
    print("=" * 60)

    # 1. 读取数据库中的所有分块
    db = SessionLocal()
    docs = {d.id: d for d in db.query(Document).all()}
    chunks = db.query(DocChunk).order_by(DocChunk.document_id, DocChunk.chunk_index).all()
    db.close()
    print(f"数据库文档数: {len(docs)}, 分块数: {len(chunks)}")
    if not chunks:
        print("数据库中没有分块，退出")
        return

    # 防护：分块内容为空时重建出的索引无法检索（历史故障根因），直接报错退出
    empty_by_doc = {}
    for c in chunks:
        if not c.content or not c.content.strip():
            empty_by_doc.setdefault(c.document_id, 0)
            empty_by_doc[c.document_id] += 1
    if empty_by_doc:
        print("✗ 检测到内容为空的分块，重建索引无意义（会清空现有可用索引！）:")
        for doc_id, cnt in empty_by_doc.items():
            title = docs.get(doc_id).title if doc_id in docs else "?"
            print(f"    doc_{doc_id} ({title}): {cnt} 个空分块")
        print("   请先对这些文档执行重新索引（POST /api/v1/documents/{doc_id}/reindex）填充分块内容，再运行本脚本。")
        return

    # 2. 备份并清空旧索引
    faiss_dir = os.path.join(settings.CHROMA_PERSIST_DIR, "faiss_index")
    backup_suffix = time.strftime("%Y%m%d_%H%M%S")
    for path in (faiss_dir, BM25_INDEX_PATH):
        if os.path.exists(path):
            backup = f"{path}.bak_{backup_suffix}"
            os.rename(path, backup)
            print(f"已备份旧索引: {backup}")

    # 3. 构建新索引
    from app.db.chroma_client import FaissVectorStore
    vs = FaissVectorStore()  # 旧文件已移除，创建空索引
    bm = BM25Retriever()

    embeddings_client = get_embeddings()

    ids = []
    vecs = []
    contents = []
    metadatas = []
    bm_chunks = []

    print(f"开始向量化 {len(chunks)} 个分块...")
    t0 = time.time()
    batch = 20
    for i in range(0, len(chunks), batch):
        group = chunks[i:i + batch]
        texts = [c.content for c in group]
        embs = embeddings_client.embed_documents(texts)
        for c, emb in zip(group, embs):
            doc = docs.get(c.document_id)
            cid = f"doc_{c.document_id}_chunk_{c.chunk_index}"
            meta = {
                "document_id": c.document_id,
                "document_name": doc.title if doc else "",
                "chapter": c.chapter or "",
                "page": c.page_start or 1,
                "security_level": doc.security_level if doc else 1,
                "category_id": doc.category_id or 0,
                "token_count": c.token_count or 0,
                "chunk_index": c.chunk_index,
            }
            ids.append(cid)
            vecs.append(emb)
            contents.append(c.content)
            metadatas.append(meta)
            bm_chunks.append({
                "chunk_id": cid,
                "document_id": c.document_id,
                "document_name": doc.title if doc else "",
                "chapter": c.chapter or "",
                "page": c.page_start or 1,
                "content": c.content,
                # 必须带上密级，否则 BM25 检索时密级过滤会 fallback 为 1（公开），
                # 导致高密级文档的 BM25 召回泄露给低密级用户
                "security_level": doc.security_level if doc else 1,
                "token_count": c.token_count or 0,
            })
        print(f"  [{min(i + batch, len(chunks))}/{len(chunks)}] 已向量化")
        time.sleep(0.1)

    print(f"向量化完成，耗时 {time.time() - t0:.1f}s")

    vs.add_embeddings(ids=ids, embeddings=vecs, documents=contents, metadatas=metadatas)
    print(f"FAISS 索引写入完成: {vs.count()} 个向量")

    bm.build_index(bm_chunks)
    bm.save(BM25_INDEX_PATH)
    print(f"BM25 索引写入完成: {bm.chunk_count} 个分块")

    # 4. 验证
    print("\n验证:")
    for doc_id in sorted(set(c.document_id for c in chunks)):
        cnt = sum(1 for k in vs._id_to_idx if k.startswith(f"doc_{doc_id}_"))
        bcnt = sum(1 for c in bm._chunks if c.get("document_id") == doc_id)
        title = docs.get(doc_id).title if doc_id in docs else "?"
        print(f"  doc_{doc_id} ({title}): FAISS={cnt} BM25={bcnt}")

    print("\n✓ 重建完成。请重启后端服务使新索引生效。")


if __name__ == "__main__":
    main()
