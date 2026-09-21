# ============================================================
# 向量数据库客户端（支持多种后端）
# 首选 ChromaDB，降级为 FAISS（兼容旧版 Python/SQLite）
# ============================================================

import os
import pickle
import threading
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

import numpy as np

from app.core.config import settings


# ==================== 抽象接口 ====================

class BaseVectorStore(ABC):
    """向量存储抽象接口"""

    @abstractmethod
    def add_embeddings(
        self, ids: List[str], embeddings: List[List[float]],
        documents: List[str], metadatas: Optional[List[Dict]] = None,
    ) -> None: ...

    @abstractmethod
    def search(
        self, query_embedding: List[float], top_k: int = 20,
        where: Optional[Dict] = None,
    ) -> Dict: ...

    @abstractmethod
    def delete_by_ids(self, ids: List[str]) -> None: ...

    @abstractmethod
    def delete_by_filter(self, where: Dict) -> None: ...

    @abstractmethod
    def count(self) -> int: ...


# ==================== ChromaDB 实现 ====================

class ChromaVectorStore(BaseVectorStore):
    """ChromaDB 向量存储（推荐）"""

    def __init__(self):
        self._init_chromadb()

    def _init_chromadb(self):
        import chromadb

        self._client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=chromadb.Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
        self._collection = self._client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"description": "企业制度文档向量库"},
        )

    def add_embeddings(self, ids, embeddings, documents, metadatas=None):
        self._collection.add(
            ids=ids, embeddings=embeddings,
            documents=documents,
            metadatas=metadatas or [{} for _ in ids],
        )

    def search(self, query_embedding, top_k=20, where=None):
        raw = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k, where=where,
            include=["documents", "metadatas", "distances"],
        )
        # 统一分数语义：scores 越大越相似（ChromaDB distances 越小越相似）
        raw["scores"] = [
            [1.0 / (1.0 + d) if d else 1.0 for d in dists]
            for dists in raw.get("distances", [[]])
        ]
        return raw

    def delete_by_ids(self, ids):
        if ids:
            self._collection.delete(ids=ids)

    def delete_by_filter(self, where):
        self._collection.delete(where=where)

    def count(self):
        return self._collection.count()


# ==================== FAISS 实现（降级方案）====================

class FaissVectorStore(BaseVectorStore):
    """
    FAISS 向量存储（兼容旧版 Python/SQLite）

    约定：search() 返回的 scores 为"越大越相似"（已映射到 [0,1]），
    与 ChromaVectorStore 的分数语义保持一致。
    """

    def __init__(self):
        self._index = None
        self._dimension = settings.EMBEDDING_DIMENSION
        self._id_to_idx: Dict[str, int] = {}
        self._idx_to_meta: Dict[int, Dict] = {}
        self._idx_to_doc: Dict[int, str] = {}
        self._idx_to_emb: Dict[int, List[float]] = {}
        self._lock = threading.Lock()
        self._save_path = os.path.join(settings.CHROMA_PERSIST_DIR, "faiss_index")
        self._load_or_create()

    def _load_or_create(self):
        os.makedirs(self._save_path, exist_ok=True)
        index_file = os.path.join(self._save_path, "index.faiss")
        meta_file = os.path.join(self._save_path, "metadata.pkl")

        if os.path.exists(index_file) and os.path.exists(meta_file):
            import faiss
            self._index = faiss.read_index(index_file)
            with open(meta_file, "rb") as f:
                data = pickle.load(f)
                self._id_to_idx = data.get("id_to_idx", {})
                self._idx_to_meta = data.get("idx_to_meta", {})
                self._idx_to_doc = data.get("idx_to_doc", {})
                self._idx_to_emb = data.get("idx_to_emb", {})
        else:
            self._create_empty_index()

    def _create_empty_index(self):
        import faiss
        self._index = faiss.IndexFlatIP(self._dimension)  # 内积相似度
        self._id_to_idx = {}
        self._idx_to_meta = {}
        self._idx_to_doc = {}
        self._idx_to_emb = {}

    def _save(self):
        import faiss
        faiss.write_index(self._index, os.path.join(self._save_path, "index.faiss"))
        with open(os.path.join(self._save_path, "metadata.pkl"), "wb") as f:
            pickle.dump({
                "id_to_idx": self._id_to_idx,
                "idx_to_meta": self._idx_to_meta,
                "idx_to_doc": self._idx_to_doc,
                "idx_to_emb": self._idx_to_emb,
            }, f)

    def add_embeddings(self, ids, embeddings, documents, metadatas=None):
        import faiss
        import numpy as np

        vectors = np.array(embeddings, dtype=np.float32)
        # 归一化用于内积=余弦相似度
        faiss.normalize_L2(vectors)

        with self._lock:
            # 幂等：已存在的 chunk_id 先从映射中清除（旧向量行稍后随重建丢弃）
            has_dup = False
            for cid in ids:
                if cid in self._id_to_idx:
                    old_idx = self._id_to_idx[cid]
                    self._idx_to_meta.pop(old_idx, None)
                    self._idx_to_doc.pop(old_idx, None)
                    self._idx_to_emb.pop(old_idx, None)
                    del self._id_to_idx[cid]
                    has_dup = True

            # 追加新向量行
            start_idx = self._index.ntotal
            self._index.add(vectors)

            for i, cid in enumerate(ids):
                idx = start_idx + i
                self._id_to_idx[cid] = idx
                self._idx_to_meta[idx] = metadatas[i] if metadatas else {}
                self._idx_to_doc[idx] = documents[i]
                self._idx_to_emb[idx] = embeddings[i]

            if has_dup:
                # 存在被替换的旧行时整体重建，避免索引中出现孤儿行
                self._rebuild_index()
            else:
                self._save()

    def search(self, query_embedding, top_k=20, where=None):
        import faiss
        import numpy as np

        vec = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(vec)

        with self._lock:
            search_k = min(top_k * 3, self._index.ntotal) if where else top_k
            if self._index.ntotal == 0 or search_k == 0:
                return {"ids": [[]], "scores": [[]], "distances": [[]],
                        "documents": [[]], "metadatas": [[]]}

            distances, indices = self._index.search(vec, search_k)

            ids_list = []
            docs_list = []
            metas_list = []
            scores_list = []

            for i, idx in enumerate(indices[0]):
                if idx < 0:
                    continue
                chunk_id = self._id_to_idx_reverse().get(idx, f"unk_{idx}")
                meta = self._idx_to_meta.get(idx, {})

                # 过滤
                if where and not self._match_filter(meta, where):
                    continue

                ids_list.append(chunk_id)
                docs_list.append(self._idx_to_doc.get(idx, ""))
                metas_list.append(meta)
                # 内积相似度映射到 [0,1]（越大越相似）
                ip = float(distances[0][i])
                scores_list.append((ip + 1.0) / 2.0)

                if len(ids_list) >= top_k:
                    break

            return {
                "ids": [ids_list],
                "scores": [scores_list],
                "distances": [scores_list],  # 兼容旧字段名（语义已统一为相似度）
                "documents": [docs_list],
                "metadatas": [metas_list],
            }

    def _id_to_idx_reverse(self):
        return {v: k for k, v in self._id_to_idx.items()}

    def _match_filter(self, meta: Dict, where: Dict) -> bool:
        if "$and" in where:
            return all(self._match_filter(meta, cond) for cond in where["$and"])
        for key, condition in where.items():
            if key.startswith("$"):
                continue
            meta_val = meta.get(key)
            if isinstance(condition, dict):
                if "$lte" in condition and meta_val > condition["$lte"]:
                    return False
                if "$gte" in condition and meta_val < condition["$gte"]:
                    return False
                if "$in" in condition and meta_val not in condition["$in"]:
                    return False
                if "$ne" in condition and meta_val == condition["$ne"]:
                    return False
            elif meta_val != condition:
                return False
        return True

    def delete_by_ids(self, ids):
        import faiss
        import numpy as np

        with self._lock:
            removed = False
            for cid in ids:
                if cid in self._id_to_idx:
                    del self._idx_to_meta[self._id_to_idx[cid]]
                    del self._idx_to_doc[self._id_to_idx[cid]]
                    del self._idx_to_emb[self._id_to_idx[cid]]
                    del self._id_to_idx[cid]
                    removed = True
            if removed:
                self._rebuild_index()

    def delete_by_filter(self, where):
        with self._lock:
            to_remove = []
            for idx, meta in self._idx_to_meta.items():
                if self._match_filter(meta, where):
                    to_remove.append(idx)

            if to_remove:
                for idx in to_remove:
                    del self._idx_to_meta[idx]
                    del self._idx_to_doc[idx]
                    del self._idx_to_emb[idx]
                self._id_to_idx = {k: v for k, v in self._id_to_idx.items()
                                  if v not in to_remove}
                self._rebuild_index()

    def _rebuild_index(self):
        """基于保留的 embedding 真正重建 FAISS 索引（不丢失数据）"""
        import faiss
        import numpy as np

        new_index = faiss.IndexFlatIP(self._dimension)
        new_id_to_idx = {}
        new_idx_to_meta = {}
        new_idx_to_doc = {}
        new_idx_to_emb = {}

        for cid, old_idx in self._id_to_idx.items():
            emb = self._idx_to_emb.get(old_idx)
            if emb is None:
                continue  # 没有原始向量则跳过（防御）
            vec = np.array([emb], dtype=np.float32)
            faiss.normalize_L2(vec)
            new_idx = new_index.ntotal
            new_index.add(vec)
            new_id_to_idx[cid] = new_idx
            new_idx_to_meta[new_idx] = self._idx_to_meta.get(old_idx, {})
            new_idx_to_doc[new_idx] = self._idx_to_doc.get(old_idx, "")
            new_idx_to_emb[new_idx] = emb

        self._index = new_index
        self._id_to_idx = new_id_to_idx
        self._idx_to_meta = new_idx_to_meta
        self._idx_to_doc = new_idx_to_doc
        self._idx_to_emb = new_idx_to_emb
        self._save()

    def count(self):
        return len(self._id_to_idx)


# ==================== 工厂函数 ====================

_vector_store: Optional[BaseVectorStore] = None


def get_vector_store() -> BaseVectorStore:
    """获取向量存储实例（自动选择可用后端）"""
    global _vector_store
    if _vector_store is not None:
        return _vector_store

    # 优先尝试 ChromaDB
    try:
        import sqlite3
        if sqlite3.sqlite_version_info >= (3, 35, 0):
            _vector_store = ChromaVectorStore()
            return _vector_store
    except Exception:
        pass

    # 降级为 FAISS
    _vector_store = FaissVectorStore()
    return _vector_store
