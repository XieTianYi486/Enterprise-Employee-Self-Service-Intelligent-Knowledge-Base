# ============================================================
# 聊天服务层 —— RAG 问答核心编排
# 流程：查询处理 → 混合检索 → 重排序 → Prompt组装 → LLM生成
# ============================================================

import json
import logging
import time
import traceback
import uuid as uuid_lib
from typing import AsyncGenerator, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import LLMException, RetrievalException
from app.models.chat import ChatSession, ChatMessage, ChatLog
from app.models.document import Document
from app.rag.retrievers.hybrid_retriever import get_hybrid_retriever
from app.rag.embeddings.dashscope_embeddings import get_embeddings
from app.rag.llm.dashscope_llm import get_llm
from app.rag.reranker.llm_reranker import get_reranker
from app.rag.prompts.chat_prompt import build_chat_messages
from app.rag.query_processor.intent_recognition import (
    detect_intent, get_greeting_response, get_rejected_response,
)
from app.rag.query_processor.query_rewrite import get_query_rewriter
from app.db.cache import cache
from app.db.sqlite import SessionLocal

logger = logging.getLogger(__name__)


class ChatService:
    """问答服务（编排完整 RAG 流程）"""

    def __init__(self):
        self.hybrid = get_hybrid_retriever()
        self.llm = get_llm()
        self.reranker = get_reranker()

    # ==================== 问答缓存 ====================

    @staticmethod
    def _get_cached_answer(question: str, security_level: int) -> Optional[Dict]:
        """读取单轮问答缓存（命中返回 {answer, sources}，未命中返回 None）"""
        key = cache.make_key(question, security_level, prefix="qa")
        cached = cache.get_from_memory(key)
        if cached is None:
            cached = cache.get_from_disk(key)
        return cached

    @staticmethod
    def _store_cached_answer(
        question: str, security_level: int, answer: str, sources: list
    ) -> None:
        """写入单轮问答缓存（内存 + 磁盘，TTL 取配置 CACHE_TTL_ANSWER）"""
        key = cache.make_key(question, security_level, prefix="qa")
        payload = {"answer": answer, "sources": sources}
        cache.set_to_memory(key, payload)
        cache.set_to_disk(key, payload, ttl=settings.CACHE_TTL_ANSWER)

    # ==================== 非流式问答 ====================

    def ask(
        self,
        question: str,
        security_level: int = 1,
        category_ids: Optional[List[int]] = None,
        chat_history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        同步问答（非流式）

        返回: {
            "answer": str, "sources": list, "usage": dict, "latency": dict
        }
        """
        t_start = time.time()

        # === 第0步：意图识别 ===
        intent = detect_intent(question)
        if intent == "greeting":
            return self._fast_response(get_greeting_response(question))
        if intent == "rejected":
            return self._fast_response(get_rejected_response())

        # === 第0.25步：问答缓存（仅单轮对话；多轮历史影响答案，不缓存）===
        cache_key = None
        if not chat_history:
            cached = self._get_cached_answer(question, security_level)
            if cached:
                return {
                    "answer": cached["answer"],
                    "sources": cached.get("sources", []),
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "latency": {
                        "retrieval_ms": 0, "rerank_ms": 0, "llm_ms": 0,
                        "total_ms": round((time.time() - t_start) * 1000),
                        "cache_hit": True,
                    },
                }
            cache_key = cache.make_key(question, security_level, prefix="qa")

        # === 第0.5步：查询改写 ===
        query_rewriter = get_query_rewriter()
        rewrite_result = query_rewriter.rewrite(question, chat_history)
        search_query = rewrite_result["rewritten"]

        # === 第1步：混合检索（主查询 + 改写变体多查询增强）===
        # 单个变体检索失败时降级跳过，仅当全部查询失败才视为检索失败
        t_retrieval_start = time.time()
        queries = [search_query]
        for v in rewrite_result.get("variants", [])[:2]:
            if v and v != search_query:
                queries.append(v)
        try:
            candidates, query_errors = self._multi_query_search(
                queries, security_level, settings.FUSION_TOP_K
            )
            if not candidates and query_errors:
                raise RetrievalException("知识库检索失败: " + "; ".join(query_errors))
        except RetrievalException:
            raise
        except Exception as e:
            raise RetrievalException(f"知识库检索失败: {str(e)}")
        t_retrieval = (time.time() - t_retrieval_start) * 1000

        # === 第1.5步：发布/密级二次过滤（仅允许已通过审核且密级内的文档）===
        visible_ids = self._visible_doc_ids(security_level)
        candidates = [c for c in candidates if c.get("document_id") in visible_ids]

        # === 第2步：拒答判定（无候选，或向量绝对相似度整体低于阈值）===
        # 融合分数经相对归一化不能当阈值用；raw_score 是保留的向量绝对
        # 相似度（[0,1]，ChromaDB/FAISS 已统一语义），可用于硬阈值判定。
        # 纯 BM25 来源候选无 raw_score，不参与判定（避免误伤纯关键词命中）。
        max_sim = self._max_absolute_similarity(candidates)
        if not candidates or (
            max_sim is not None and max_sim < settings.SIMILARITY_THRESHOLD
        ):
            return {
                "answer": "抱歉，知识库中未找到相关信息，建议您咨询 HR 部门或查看完整制度文档。",
                "sources": [],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "latency": {
                    "retrieval_ms": round(t_retrieval),
                    "rerank_ms": 0,
                    "llm_ms": 0,
                    "total_ms": round((time.time() - t_start) * 1000),
                },
            }

        # === 第3步：LLM 重排序（候选 -> 最相关 Top-N）===
        t_rerank_start = time.time()
        rerank_candidates = candidates[:settings.RERANK_CANDIDATES]
        top_chunks = self.reranker.rerank(question, rerank_candidates)
        top_chunks = top_chunks[:settings.RERANK_TOP_N]
        t_rerank = (time.time() - t_rerank_start) * 1000

        # === 第4步：组装 Prompt ===
        messages = build_chat_messages(
            question=question,
            context_chunks=top_chunks,
            chat_history=chat_history,
        )

        # === 第5步：LLM 生成（无 API Key / 失败 → 降级检索直出）===
        t_llm_start = time.time()
        llm_fallback_used = False
        if not settings.DASHSCOPE_API_KEY:
            llm_fallback_used = True
            result = {"content": self._build_fallback_answer(question, top_chunks), "usage": {}}
        else:
            try:
                result = self.llm.chat(messages)
            except LLMException:
                logger.warning("LLM 调用失败，降级为检索直出")
                llm_fallback_used = True
                result = {"content": self._build_fallback_answer(question, top_chunks), "usage": {}}
        t_llm = (time.time() - t_llm_start) * 1000

        # === 构建来源信息 ===
        sources = []
        for c in top_chunks:
            sources.append({
                "document_id": c.get("document_id", 0),
                "document_name": c.get("document_name", ""),
                "chapter": c.get("chapter", ""),
                "page": c.get("page", 1),
                "snippet": c.get("content", "")[:200],
                "score": round(c.get("score", 0), 4),
            })

        # === 总耗时 ===
        total_ms = round((time.time() - t_start) * 1000)

        # 写入单轮问答缓存（供后续相同问题直接命中）
        if cache_key:
            self._store_cached_answer(
                question, security_level, result["content"], sources
            )

        return {
            "answer": result["content"],
            "sources": sources,
            "similarity": round(max_sim, 4) if max_sim is not None else None,
            "usage": result.get("usage", {}),
            "status": "llm_fallback" if llm_fallback_used else "ok",
            "suggested_actions": self._suggest_actions(question),
            "latency": {
                "retrieval_ms": round(t_retrieval),
                "rerank_ms": round(t_rerank),
                "llm_ms": round(t_llm),
                "total_ms": total_ms,
            },
        }

    # ==================== 流式问答 ====================

    async def ask_stream(
        self,
        question: str,
        security_level: int = 1,
        chat_history: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[Dict, None]:
        """
        流式问答（SSE）

        Yields:
            {"type": "token", "data": str} |
            {"type": "sources", "data": list} |
            {"type": "done", "data": dict} |
            {"type": "error", "data": str}
        """
        t_start = time.time()

        # === 第0步：意图识别 ===
        intent = detect_intent(question)
        if intent == "greeting":
            yield {"type": "token", "data": get_greeting_response(question)}
            yield {"type": "sources", "data": []}
            yield {"type": "done", "data": {
                "full_answer": get_greeting_response(question),
                "total_tokens": 0,
                "latency": {"retrieval_ms": 0, "llm_ms": 0, "total_ms": 0},
            }}
            return
        if intent == "rejected":
            yield {"type": "token", "data": get_rejected_response()}
            yield {"type": "sources", "data": []}
            yield {"type": "done", "data": {
                "full_answer": get_rejected_response(),
                "total_tokens": 0,
                "latency": {"retrieval_ms": 0, "llm_ms": 0, "total_ms": 0},
            }}
            return

        # === 第0.25步：问答缓存（仅单轮对话；多轮历史影响答案，不缓存）===
        cache_key = None
        if not chat_history:
            cached = self._get_cached_answer(question, security_level)
            if cached:
                yield {"type": "token", "data": cached["answer"]}
                yield {"type": "sources", "data": cached.get("sources", [])}
                yield {"type": "done", "data": {
                    "full_answer": cached["answer"],
                    "total_tokens": len(cached["answer"]) // 3,  # 粗略估算
                    "status": "cache_hit",
                    "latency": {
                        "retrieval_ms": 0, "llm_ms": 0,
                        "total_ms": round((time.time() - t_start) * 1000),
                    },
                }}
                return
            cache_key = cache.make_key(question, security_level, prefix="qa")

        # === 第0.5步：查询改写 ===
        query_rewriter = get_query_rewriter()
        rewrite_result = query_rewriter.rewrite(question, chat_history)
        search_query = rewrite_result["rewritten"]

        # === 第1步：混合检索（主查询 + 改写变体多查询增强）===
        t_retrieval_start = time.time()
        queries = [search_query]
        for v in rewrite_result.get("variants", [])[:2]:
            if v and v != search_query:
                queries.append(v)
        try:
            candidates, query_errors = self._multi_query_search(
                queries, security_level, settings.FUSION_TOP_K
            )
            if not candidates and query_errors:
                raise RetrievalException("知识库检索失败: " + "; ".join(query_errors))
        except Exception as e:
            yield {"type": "error", "data": f"检索失败: {str(e)}"}
            return
        t_retrieval = (time.time() - t_retrieval_start) * 1000

        # === 第1.5步：发布/密级二次过滤 ===
        visible_ids = self._visible_doc_ids(security_level)
        candidates = [c for c in candidates if c.get("document_id") in visible_ids]

        # === 第2步：拒答判定（无候选，或向量绝对相似度整体低于阈值）===
        max_sim = self._max_absolute_similarity(candidates)
        if not candidates or (
            max_sim is not None and max_sim < settings.SIMILARITY_THRESHOLD
        ):
            total_ms = round((time.time() - t_start) * 1000)
            yield {
                "type": "done",
                "data": {
                    "answer": "抱歉，知识库中未找到相关信息，建议您咨询 HR 部门或查看完整制度文档。",
                    "sources": [],
                    "status": "not_found",
                    "similarity": round(max_sim, 4) if max_sim is not None else None,
                    "latency": {
                        "retrieval_ms": round(t_retrieval), "llm_ms": 0,
                        "total_ms": total_ms,
                    },
                }
            }
            return

        # === 第3步：LLM 重排序 ===
        rerank_candidates = candidates[:settings.RERANK_CANDIDATES]
        top_chunks = self.reranker.rerank(question, rerank_candidates)
        top_chunks = top_chunks[:settings.RERANK_TOP_N]
        sources = [
            {
                "document_id": c.get("document_id", 0),
                "document_name": c.get("document_name", ""),
                "chapter": c.get("chapter", ""),
                "page": c.get("page", 1),
                "snippet": c.get("content", "")[:200],
                "score": round(c.get("score", 0), 4),
            }
            for c in top_chunks
        ]

        # === 第4步：组装 Prompt ===
        messages = build_chat_messages(
            question=question,
            context_chunks=top_chunks,
            chat_history=chat_history,
        )

        # === 第5步：流式 LLM 生成（无 API Key / 调用失败 → 降级检索直出）===
        t_llm_start = time.time()
        full_answer = ""
        llm_fallback_used = False
        if not settings.DASHSCOPE_API_KEY:
            # 未配置大模型密钥：直接走检索直出（知识模块不依赖 LLM 也可用）
            llm_fallback_used = True
        else:
            try:
                async for token in self.llm.chat_stream(messages):
                    full_answer += token
                    yield {"type": "token", "data": token}
            except LLMException as e:
                if full_answer:
                    # 已输出部分内容后才失败：无法回退，按错误处理
                    yield {"type": "error", "data": f"AI 服务调用失败: {str(e)}"}
                    return
                logger.warning(f"LLM 调用失败，降级为检索直出: {e}")
                llm_fallback_used = True
        t_llm = (time.time() - t_llm_start) * 1000

        if llm_fallback_used:
            full_answer = self._build_fallback_answer(question, top_chunks)
            yield {"type": "token", "data": full_answer}

        # 写入单轮问答缓存（供后续相同问题直接命中）
        if cache_key:
            self._store_cached_answer(question, security_level, full_answer, sources)

        # === 发送来源 ===
        yield {"type": "sources", "data": sources}

        # === 完成 ===
        total_ms = round((time.time() - t_start) * 1000)
        yield {
            "type": "done",
            "data": {
                "full_answer": full_answer,
                "total_tokens": len(full_answer) // 3,  # 粗略估算
                "similarity": round(max_sim, 4) if max_sim is not None else None,
                "status": "llm_fallback" if llm_fallback_used else "ok",
                "suggested_actions": self._suggest_actions(question),
                "latency": {
                    "retrieval_ms": round(t_retrieval),
                    "llm_ms": round(t_llm),
                    "total_ms": total_ms,
                },
            }
        }

    # ==================== 无 LLM 降级与流程建议 ====================

    @staticmethod
    def _build_fallback_answer(question: str, top_chunks: List[Dict]) -> str:
        """
        构建"检索直出"降级答案：LLM 不可用时（未配置 API Key / 调用失败），
        直接返回检索命中的原文片段并标注出处，保证知识模块可用。

        设计原则：大模型是增强能力而非单点故障——无 LLM 时问答
        仍可提供服务（返回可溯源的原始条款，而非生成内容）。
        """
        if not top_chunks:
            return "抱歉，知识库中未找到相关信息，建议您咨询 HR 部门或查看完整制度文档。"
        lines = [
            "> ⚠️ 智能生成服务暂不可用，以下为知识库检索到的相关内容原文，请以制度原文为准：",
            "",
        ]
        for i, c in enumerate(top_chunks, 1):
            doc = c.get("document_name", "未知文档")
            chapter = c.get("chapter") or ""
            page = c.get("page")
            loc = f" 第{chapter}章" if chapter else ""
            if page:
                loc += f"（第{page}页）"
            snippet = (c.get("content") or "").strip()[:300]
            lines.append(f"**{i}. 《{doc}》{loc}**")
            lines.append("")
            lines.append(snippet)
            lines.append("")
        return "\n".join(lines).strip()

    @staticmethod
    def _suggest_actions(question: str) -> list:
        """
        按问题关键词给出流程跳转建议（不依赖 LLM，规则匹配）。
        用于打通「制度咨询 → 业务办理」的自助服务链路。
        """
        actions = []
        q = question or ""
        leave_words = ("请假", "年假", "事假", "病假", "调休", "婚假", "休假", "休息")
        expense_words = ("报销", "发票", "差旅", "费用", "出差", "招待")
        ticket_words = ("工单", "投诉", "反馈", "咨询", "问题反馈")
        if any(w in q for w in leave_words):
            actions.append({"type": "leave", "label": "去请假"})
        if any(w in q for w in expense_words):
            actions.append({"type": "expense", "label": "去报销"})
        if any(w in q for w in ticket_words):
            actions.append({"type": "ticket", "label": "提交工单"})
        return actions[:2]

    # ==================== 辅助方法 ====================

    @staticmethod
    def _visible_doc_ids(security_level: int) -> set:
        """
        获取当前用户可检索的文档 ID 集合。

        严格遵循企业发布流与密级控制：
        - 仅"已发布(status=1) + 已通过审核(review_status=2)"的文档可被检索
        - 且密级不得高于用户可访问的安全级别

        用于对检索召回结果做二次过滤，防止未审核/越权内容被问答引用。
        """
        db = SessionLocal()
        try:
            rows = db.query(Document.id).filter(
                Document.status == 1,
                Document.review_status == 2,
                Document.security_level <= security_level,
            ).all()
            return {r[0] for r in rows}
        finally:
            db.close()

    @staticmethod
    def _max_absolute_similarity(candidates: List[Dict]) -> Optional[float]:
        """
        候选集中"向量来源"候选的最高绝对相似度。

        raw_score 由 hybrid_retriever 保留向量检索的原始相似度（[0,1]，
        未经相对归一化），可用于 SIMILARITY_THRESHOLD 硬阈值拒答判定。
        全部候选均为纯 BM25 来源（无 raw_score）时返回 None，
        表示无法用向量阈值判定，交由重排+LLM 兜底。
        """
        scores = [
            c["raw_score"] for c in candidates
            if c.get("raw_score") is not None
        ]
        return max(scores) if scores else None

    @staticmethod
    def _fast_response(answer: str) -> Dict:
        """构建快速响应（不走 RAG 流程）"""
        return {
            "answer": answer,
            "sources": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "latency": {
                "retrieval_ms": 0, "rerank_ms": 0,
                "llm_ms": 0, "total_ms": 0,
            },
        }

    # ==================== 多查询检索 ====================

    def _multi_query_search(
        self,
        queries: List[str],
        security_level: int,
        top_k: int,
    ) -> Tuple[List[Dict], List[str]]:
        """
        对主查询及其改写变体分别执行混合检索，按 chunk_id 合并去重（保留最高分）。

        性能优化：所有查询的向量化合并为一次 Embedding API 批量调用
        （原实现逐查询向量化，N 个查询 = N 次网络往返）；
        批量调用失败时降级为逐查询检索（由 hybrid 内部向量化）。

        单个查询失败时降级跳过并记录错误，仅当全部查询失败时调用方才会判定检索失败。

        返回: (合并后的候选列表（按分数降序）, 各查询的错误信息列表)
        """
        merged: Dict[str, Dict] = {}
        errors: List[str] = []

        # 去重（保留顺序）：改写变体与原查询重复时避免重复向量化
        dedup_queries = list(dict.fromkeys(q for q in queries if q and q.strip()))

        # 批量向量化：N 个查询只发起一次 Embedding API 调用
        query_vectors = None
        try:
            query_vectors = get_embeddings().embed_queries(dedup_queries)
        except Exception as e:
            errors.append(f"批量向量化失败: {e}")

        for i, q in enumerate(dedup_queries):
            query_embedding = query_vectors[i] if query_vectors is not None else None
            try:
                results = self.hybrid.search(
                    query=q, top_k=top_k, security_level=security_level,
                    query_embedding=query_embedding,
                )
            except Exception as e:
                errors.append(str(e))
                logger.warning(f"多查询检索变体失败: {e}")
                continue
            for c in results:
                cid = c.get("chunk_id", "")
                if not cid:
                    continue
                if cid not in merged or c.get("score", 0) > merged[cid].get("score", 0):
                    merged[cid] = c
        merged_list = sorted(
            merged.values(), key=lambda x: x.get("score", 0), reverse=True
        )
        return merged_list, errors

    # ==================== 会话管理 ====================

    @staticmethod
    def save_chat_log(
        question: str,
        answer: str,
        session_id: str,
        user_id: int,
        sources: list,
        latency: dict,
        usage: dict,
    ) -> None:
        """保存问答日志到数据库（使用独立会话，失败不影响主流程）"""
        db = SessionLocal()
        try:
            # 综合判断是否真正命中：有来源 + LLM 未拒绝
            has_sources = bool(sources)
            refusal_patterns = [
                "未找到相关信息", "未找到关于", "知识库中未找到", "无法回答",
                "建议您咨询", "无法获取", "参考资料中未涉及", "未涉及",
            ]
            is_refusal = any(p in answer for p in refusal_patterns)
            is_answered = 1 if (has_sources and not is_refusal) else 0
            log = ChatLog(
                session_id=session_id,
                user_id=user_id,
                question=question,
                answer=answer,
                source_doc_ids=[s.get("document_id") for s in sources],
                is_answered=is_answered,
                retrieval_ms=latency.get("retrieval_ms", 0),
                rerank_ms=latency.get("rerank_ms", 0),
                llm_ms=latency.get("llm_ms", 0),
                total_ms=latency.get("total_ms", 0),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
            db.add(log)
            db.commit()
        except Exception:
            db.rollback()
            logger.warning(f"保存问答日志失败: {traceback.format_exc()}")
        finally:
            db.close()


# --- 全局单例 ---
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """获取聊天服务单例"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
