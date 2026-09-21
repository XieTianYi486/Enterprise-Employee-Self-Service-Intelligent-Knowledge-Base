# ============================================================
# P0 修复测试：SIMILARITY_THRESHOLD 绝对相似度拒答
# 向量候选的绝对相似度（raw_score）低于阈值时，ask() 应直接
# 拒答，不再进入重排序/LLM 生成环节
# 注：检索、可见性过滤、查询改写均打桩，不写数据库，
#     避免污染其他测试对可见文档集合的精确断言
# ============================================================

from app.core.config import settings
from app.services.chat_service import ChatService


def _make_service(monkeypatch, candidates):
    """构造 ChatService（绕过 __init__ 避免初始化真实向量库/LLM 客户端）"""
    service = object.__new__(ChatService)

    # 绕过问答缓存（避免命中开发环境的磁盘缓存干扰测试）
    monkeypatch.setattr(service, "_get_cached_answer", lambda q, l: None)
    monkeypatch.setattr(service, "_store_cached_answer", lambda *a, **k: None)

    # 打桩检索：直接返回给定候选
    monkeypatch.setattr(
        service, "_multi_query_search",
        lambda queries, security_level, top_k: (candidates, []),
    )

    # 打桩可见性过滤：候选全部视为可见（不依赖真实数据库数据）
    monkeypatch.setattr(
        service, "_visible_doc_ids",
        lambda level: {c.get("document_id") for c in candidates},
    )

    # 打桩查询改写（避免真实 LLM 调用）
    class _FakeRewriter:
        def rewrite(self, question, chat_history=None):
            return {"rewritten": question, "variants": []}

    monkeypatch.setattr(
        "app.services.chat_service.get_query_rewriter",
        lambda: _FakeRewriter(),
    )

    # 固定阈值，避免本地 .env 覆盖影响断言
    monkeypatch.setattr(settings, "SIMILARITY_THRESHOLD", 0.5)
    return service


class TestMaxAbsoluteSimilarity:
    """_max_absolute_similarity 纯函数逻辑"""

    def test_returns_max_of_vector_sourced(self):
        candidates = [
            {"chunk_id": "a", "raw_score": 0.6},
            {"chunk_id": "b", "raw_score": 0.4},
            {"chunk_id": "c"},  # 纯 BM25 来源，无 raw_score
        ]
        assert ChatService._max_absolute_similarity(candidates) == 0.6

    def test_all_bm25_returns_none(self):
        candidates = [{"chunk_id": "a"}, {"chunk_id": "b"}]
        assert ChatService._max_absolute_similarity(candidates) is None

    def test_empty_returns_none(self):
        assert ChatService._max_absolute_similarity([]) is None


class TestThresholdRefusal:
    """ask() 的拒答判定分支"""

    def test_low_similarity_refused_before_llm(self, monkeypatch):
        low_candidates = [
            {
                "chunk_id": "c1", "content": "无关内容",
                "document_id": 1, "document_name": "测试制度",
                "chapter": "", "page": 1, "score": 0.9, "raw_score": 0.25,
            }
        ]
        service = _make_service(monkeypatch, low_candidates)

        result = service.ask("公司明年战略规划是什么", security_level=1)

        assert result["sources"] == []
        assert "未找到相关信息" in result["answer"]
        assert result["latency"]["llm_ms"] == 0  # 未进入 LLM 生成环节

    def test_high_similarity_passes_threshold(self, monkeypatch):
        good_candidates = [
            {
                "chunk_id": "c1", "content": "差旅报销需提交发票与审批单。",
                "document_id": 1, "document_name": "测试制度",
                "chapter": "", "page": 1, "score": 0.9, "raw_score": 0.8,
            }
        ]
        service = _make_service(monkeypatch, good_candidates)

        # 打桩重排序与 LLM，验证阈值放行后确实走到生成环节
        class FakeReranker:
            def rerank(self, question, candidates):
                return candidates

        class FakeLLM:
            def chat(self, messages):
                return {
                    "content": "根据制度，报销需提交发票。",
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }

        # object.__new__ 创建的实例没有这些属性，用直接赋值
        service.reranker = FakeReranker()
        service.llm = FakeLLM()

        result = service.ask("报销要哪些材料", security_level=1)

        assert result["sources"]  # 带来源
        assert result["answer"] == "根据制度，报销需提交发票。"
        assert result["similarity"] == 0.8

    def test_pure_bm25_candidates_skip_threshold(self, monkeypatch):
        """纯 BM25 候选无 raw_score，不做阈值判定（避免误伤关键词命中）"""
        bm25_only = [
            {
                "chunk_id": "c1", "content": "第三条 报销流程",
                "document_id": 1, "document_name": "测试制度",
                "chapter": "", "page": 1, "score": 0.9,
            }
        ]
        service = _make_service(monkeypatch, bm25_only)

        class FakeReranker:
            def rerank(self, question, candidates):
                return candidates

        class FakeLLM:
            def chat(self, messages):
                return {
                    "content": "第三条规定的报销流程如下。",
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }

        service.reranker = FakeReranker()
        service.llm = FakeLLM()

        result = service.ask("第三条怎么规定的", security_level=1)

        assert result["sources"]
        assert result["similarity"] is None
