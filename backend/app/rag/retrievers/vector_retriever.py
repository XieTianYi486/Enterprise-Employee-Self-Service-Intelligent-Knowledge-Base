# ============================================================
# ChromaDB 向量检索器
# 封装 ChromaDB 查询，支持元数据过滤
# ============================================================

from typing import List, Dict, Optional

from app.core.config import settings
from app.db.chroma_client import get_vector_store
from app.rag.embeddings.dashscope_embeddings import get_embeddings


class VectorRetriever:
    """ChromaDB 向量检索器"""

    def __init__(self):
        self.vector_store = get_vector_store()
        self.embeddings = get_embeddings()

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        security_level: Optional[int] = None,
        doc_ids: Optional[List[int]] = None,
        category_ids: Optional[List[int]] = None,
    ) -> List[Dict]:
        """
        向量语义检索

        参数:
            query: 查询文本
            top_k: 返回数量
            security_level: 密级过滤（只返回 <= 此级别的文档）
            doc_ids: 限定文档 ID 列表
            category_ids: 限定分类 ID 列表

        返回:
            [{
                "chunk_id": str,
                "content": str,
                "document_id": int,
                "document_name": str,
                "chapter": str,
                "page": int,
                "score": float,
            }, ...]
        """
        if top_k is None:
            top_k = settings.VECTOR_TOP_K

        # 生成查询向量
        query_vector = self.embeddings.embed_query(query)

        # 构建元数据过滤条件
        where_filter = self._build_filter(
            security_level, doc_ids, category_ids
        )

        # 执行检索
        result = self.vector_store.search(
            query_embedding=query_vector,
            top_k=top_k,
            where=where_filter,
        )

        # 格式化结果
        return self._format_results(result)

    def search_by_embedding(
        self,
        embedding: List[float],
        top_k: Optional[int] = None,
        security_level: Optional[int] = None,
    ) -> List[Dict]:
        """使用已有的向量进行检索（缓存优化）"""
        if top_k is None:
            top_k = settings.VECTOR_TOP_K

        where_filter = self._build_filter(security_level)

        result = self.vector_store.search(
            query_embedding=embedding,
            top_k=top_k,
            where=where_filter,
        )

        return self._format_results(result)

    def _build_filter(
        self,
        security_level: Optional[int] = None,
        doc_ids: Optional[List[int]] = None,
        category_ids: Optional[List[int]] = None,
    ) -> Optional[Dict]:
        """构建 ChromaDB 元数据过滤条件"""
        conditions = []

        if security_level is not None:
            conditions.append({
                "security_level": {"$lte": security_level}
            })

        if doc_ids is not None and len(doc_ids) > 0:
            if len(doc_ids) == 1:
                conditions.append({"document_id": doc_ids[0]})
            else:
                conditions.append({
                    "document_id": {"$in": doc_ids}
                })

        if category_ids is not None and len(category_ids) > 0:
            if len(category_ids) == 1:
                conditions.append({"category_id": category_ids[0]})
            else:
                conditions.append({
                    "category_id": {"$in": category_ids}
                })

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _format_results(self, raw_result: Dict) -> List[Dict]:
        """
        将向量库原始结果格式化为统一结构
        scores 约定：越大越相似（ChromaDB 与 FAISS 后端已统一该语义）
        """
        results = []

        if not raw_result or "ids" not in raw_result:
            return results

        ids_list = raw_result["ids"][0] if raw_result["ids"] else []
        # 优先使用统一语义的 scores（越大越相似），旧字段 distances 作为兜底
        scores = raw_result.get("scores", [])
        scores_list = scores[0] if scores else (raw_result.get("distances") or [[]])[0]
        documents = raw_result["documents"][0] if raw_result["documents"] else []
        metadatas = raw_result["metadatas"][0] if raw_result["metadatas"] else []

        for i, chunk_id in enumerate(ids_list):
            metadata = metadatas[i] if i < len(metadatas) else {}
            score = scores_list[i] if i < len(scores_list) else 0.0

            results.append({
                "chunk_id": chunk_id,
                "content": documents[i] if i < len(documents) else "",
                "document_id": metadata.get("document_id", 0),
                "document_name": metadata.get("document_name", ""),
                "chapter": metadata.get("chapter", ""),
                "page": metadata.get("page", 1),
                "security_level": metadata.get("security_level", 1),
                "category_id": metadata.get("category_id", 0),
                "score": round(float(score), 4),
            })

        return results


# --- 全局单例 ---
_vector_retriever: Optional[VectorRetriever] = None


def get_vector_retriever() -> VectorRetriever:
    """获取向量检索器单例"""
    global _vector_retriever
    if _vector_retriever is None:
        _vector_retriever = VectorRetriever()
    return _vector_retriever
