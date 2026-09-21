# ============================================================
# 百炼 Embedding 封装（OpenAI 兼容模式）
# 使用 HTTP API 直接调用，避免 DashScope SDK 兼容性问题
# ============================================================

import time
from typing import List, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import EmbeddingException
from app.db.cache import cache


class DashScopeEmbeddings:
    """
    百炼文本嵌入服务

    使用 OpenAI 兼容 HTTP API：
    POST {base_url}/embeddings

    性能优化：
      - 持久 httpx.Client 复用连接，避免每次调用重新建立 TLS 连接
      - 查询向量走两级缓存（内存 + 磁盘），重复问题不再调用 API
      - embed_queries 将多个查询合并为一次 API 调用
    """

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        self.model = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION

        # 使用 MaaS 工作空间 OpenAI 兼容端点
        self.base_url = (
            settings.DASHSCOPE_OPENAI_BASE_URL or
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ).rstrip("/")

        if not self.api_key:
            raise EmbeddingException("未配置 DASHSCOPE_API_KEY")

        # 持久连接（httpx.Client 线程安全，问答与文档处理可并发复用）
        self._client = httpx.Client(timeout=60.0)

    def _call_api(self, inputs: List[str], text_type: str = "query") -> List[List[float]]:
        """
        调用 Embedding API

        参数:
            inputs: 文本列表
            text_type: "query" 或 "document"

        返回:
            向量列表
        """
        url = f"{self.base_url}/embeddings"

        body = {
            "model": self.model,
            "input": inputs,
        }

        # 某些 endpoint 支持 text_type 参数优化检索
        if text_type:
            body["text_type"] = text_type

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = self._client.post(url, json=body, headers=headers)

            if resp.status_code != 200:
                error_msg = resp.text[:500]
                raise EmbeddingException(
                    f"Embedding API 返回错误 ({resp.status_code}): {error_msg}"
                )

            data = resp.json()
            embeddings = [item["embedding"] for item in data["data"]]
            return embeddings

        except httpx.RequestError as e:
            raise EmbeddingException(f"Embedding API 网络请求失败: {str(e)}")

    def embed_query(self, text: str) -> List[float]:
        """对查询文本进行向量化（带缓存，重复问题不再调用 API）"""
        return self.embed_queries([text])[0]

    def embed_queries(self, texts: List[str]) -> List[List[float]]:
        """
        批量向量化多个查询文本。

        缓存命中的文本直接返回，未命中的合并为一次 API 调用
        （N 个查询只产生一次网络往返，原实现为 N 次）。
        """
        results = [[0.0] * self.dimension for _ in texts]
        missing_texts: List[str] = []
        missing_indexes: List[int] = []

        for i, raw in enumerate(texts):
            text = (raw or "").strip()
            if not text:
                continue  # 空文本保持零向量
            cached = self._cached_query_embedding(text)
            if cached is not None:
                results[i] = cached
            else:
                missing_texts.append(text)
                missing_indexes.append(i)

        if missing_texts:
            vectors = self._call_api(missing_texts, text_type="query")
            for j, (idx, vec) in enumerate(zip(missing_indexes, vectors)):
                results[idx] = vec
                self._cache_query_embedding(missing_texts[j], vec)

        return results

    def _cached_query_embedding(self, text: str) -> Optional[List[float]]:
        """读取查询向量缓存（内存 + 磁盘两级）"""
        key = cache.make_key(text, prefix="emb")
        cached = cache.get_from_memory(key)
        if cached is None:
            cached = cache.get_from_disk(key)
        return cached

    def _cache_query_embedding(self, text: str, vec: List[float]) -> None:
        """写入查询向量缓存（嵌入结果稳定，TTL 取 EMBED_CACHE_TTL）"""
        key = cache.make_key(text, prefix="emb")
        cache.set_to_memory(key, vec)
        cache.set_to_disk(key, vec, ttl=settings.EMBED_CACHE_TTL)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量对文档文本进行向量化
        百炼 API 单次调用最多支持 25 条
        """
        if not texts:
            return []

        all_embeddings = []
        batch_size = 20  # 每批 20 条，留余量

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch = [t.strip() if t and t.strip() else " " for t in batch]

            batch_embeddings = self._call_api(batch, text_type="document")
            all_embeddings.extend(batch_embeddings)

            # 速率限制
            if i + batch_size < len(texts):
                time.sleep(0.1)

        return all_embeddings


# --- 全局单例 ---
_embeddings_instance: Optional[DashScopeEmbeddings] = None


def get_embeddings() -> DashScopeEmbeddings:
    """获取嵌入服务单例"""
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = DashScopeEmbeddings()
    return _embeddings_instance
