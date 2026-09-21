# ============================================================
# BM25 关键词检索器
# 使用 rank_bm25 库实现标准 BM25 算法
# 与旧项目用 jieba 分词 + FAISS 模拟的方式完全区分开
# ============================================================

import pickle
import os
from typing import List, Dict, Tuple, Optional

from rank_bm25 import BM25Okapi

from app.core.config import settings


class BM25Retriever:
    """
    BM25 关键词检索器

    特性：
    - 使用 rank_bm25 库的标准 BM25Okapi 实现
    - 支持中文（通过外部分词器）
    - 索引可持久化到磁盘（pickle）
    - 支持按元数据过滤
    """

    def __init__(self, index_path: Optional[str] = None):
        """
        初始化 BM25 检索器

        参数:
            index_path: 索引持久化路径（可选）
        """
        self._bm25: Optional[BM25Okapi] = None
        self._chunks: List[Dict] = []  # 存储完整的 chunk 信息
        self._tokenized_corpus: List[List[str]] = []
        self._index_path = index_path

    # ---------- 分词 ----------

    def _tokenize(self, text: str) -> List[str]:
        """
        中文分词
        优先使用 jieba，若未安装则降级为字符级分词
        """
        try:
            import jieba
            return list(jieba.cut_for_search(text))
        except ImportError:
            # 降级：简单字符+词组分词
            return self._simple_tokenize(text)

    def _simple_tokenize(self, text: str) -> List[str]:
        """
        简单分词（不回退时使用）
        按字符切分 + 提取连续字母数字
        """
        import re
        tokens = []
        # 提取连续字母数字作为词组
        for match in re.finditer(r'[a-zA-Z0-9]+', text):
            tokens.append(match.group())
        # 对中文字符逐字切分
        for char in text:
            if '一' <= char <= '鿿':
                tokens.append(char)
        return tokens

    # ---------- 索引构建 ----------

    def build_index(self, chunks: List[Dict]) -> None:
        """
        构建 BM25 索引

        参数:
            chunks: 文档分块列表，每个包含 content 和元数据
        """
        if not chunks:
            return

        self._chunks = chunks

        # 对所有 chunk 进行分词
        self._tokenized_corpus = [
            self._tokenize(chunk["content"]) for chunk in chunks
        ]

        # 构建 BM25 索引
        self._bm25 = BM25Okapi(self._tokenized_corpus)

    def add_chunks(self, new_chunks: List[Dict]) -> None:
        """
        增量添加 chunk 到索引

        参数:
            new_chunks: 新增的文档分块列表
        """
        if not new_chunks:
            return

        self._chunks.extend(new_chunks)

        # 对新 chunk 分词
        new_tokenized = [
            self._tokenize(chunk["content"]) for chunk in new_chunks
        ]
        self._tokenized_corpus.extend(new_tokenized)

        # 重建索引（BM25Okapi 不支持增量更新）
        self._bm25 = BM25Okapi(self._tokenized_corpus)

    def remove_by_document_id(self, document_id: int) -> int:
        """
        按文档 ID 移除 chunks 并重建索引

        参数:
            document_id: 文档ID

        返回:
            移除的 chunk 数量
        """
        before = len(self._chunks)
        self._chunks = [
            c for c in self._chunks
            if c.get("document_id") != document_id
        ]
        after = len(self._chunks)

        if before != after:
            # 重建索引
            self._tokenized_corpus = [
                self._tokenize(c["content"]) for c in self._chunks
            ]
            self._bm25 = BM25Okapi(self._tokenized_corpus) if self._tokenized_corpus else None

        return before - after

    # ---------- 检索 ----------

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        security_level: Optional[int] = None,
        doc_ids_filter: Optional[List[int]] = None,
    ) -> List[Tuple[Dict, float]]:
        """
        BM25 关键词检索

        参数:
            query: 查询文本
            top_k: 返回数量
            security_level: 密级过滤（只返回 security_level <= 此值的文档）
            doc_ids_filter: 限定文档 ID 范围（可选）

        返回:
            [(chunk_dict, score), ...] 按 BM25 分降序排列
        """
        if not self._bm25 or not self._tokenized_corpus:
            return []

        if top_k is None:
            top_k = settings.BM25_TOP_K

        # 对查询分词
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # BM25 计算得分
        scores = self._bm25.get_scores(query_tokens)

        # 按得分排序
        ranked_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )

        results = []
        for idx in ranked_indices:
            chunk = self._chunks[idx]

            # 应用密级过滤：只返回密级 <= 用户密级的文档
            if security_level is not None:
                chunk_level = chunk.get("security_level", 1)
                if chunk_level > security_level:
                    continue

            # 应用文档 ID 过滤
            if doc_ids_filter is not None:
                if chunk.get("document_id") not in doc_ids_filter:
                    continue

            # 归一化得分到 [0, 1]
            max_score = scores[ranked_indices[0]] if ranked_indices else 1
            norm_score = scores[idx] / max_score if max_score > 0 else 0

            results.append((chunk, norm_score))

            if len(results) >= top_k:
                break

        return results

    # ---------- 持久化 ----------

    def save(self, path: str) -> None:
        """保存索引到磁盘"""
        data = {
            "chunks": self._chunks,
            "tokenized_corpus": self._tokenized_corpus,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)

    def load(self, path: str) -> bool:
        """从磁盘加载索引"""
        if not os.path.exists(path):
            return False
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            self._chunks = data["chunks"]
            self._tokenized_corpus = data["tokenized_corpus"]
            if self._tokenized_corpus:
                self._bm25 = BM25Okapi(self._tokenized_corpus)
            return True
        except Exception:
            return False

    @property
    def is_empty(self) -> bool:
        """索引是否为空"""
        return self._bm25 is None or len(self._chunks) == 0

    @property
    def chunk_count(self) -> int:
        """索引中的 chunk 数量"""
        return len(self._chunks)


# --- 全局单例 ---
_bm25_instance: Optional[BM25Retriever] = None

# BM25 索引持久化路径
BM25_INDEX_PATH = os.path.join(
    os.path.dirname(settings.CHROMA_PERSIST_DIR),
    "bm25_index.pkl"
)


def get_bm25_retriever() -> BM25Retriever:
    """获取 BM25 检索器单例"""
    global _bm25_instance
    if _bm25_instance is None:
        _bm25_instance = BM25Retriever()
        # 尝试加载已有索引
        _bm25_instance.load(BM25_INDEX_PATH)
    return _bm25_instance


def save_bm25_index() -> None:
    """持久化 BM25 索引"""
    if _bm25_instance and not _bm25_instance.is_empty:
        _bm25_instance.save(BM25_INDEX_PATH)
