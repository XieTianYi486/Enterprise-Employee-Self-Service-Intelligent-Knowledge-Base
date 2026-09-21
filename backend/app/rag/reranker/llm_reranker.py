# ============================================================
# LLM 重排序器
# 使用 LLM 对混合检索候选分块按与问题的相关性重新排序
# （替代专用 rerank API：百炼 gte-rerank 需要额外开通权限）
# ============================================================

import json
import logging
import re
from typing import List, Dict, Optional

from app.rag.llm.dashscope_llm import get_llm
from app.core.config import settings

logger = logging.getLogger(__name__)

# 每个候选分块送入 LLM 的最大字符数（控制重排 prompt 长度与延迟）
MAX_CHUNK_CHARS = 150

RERANK_SYSTEM_PROMPT = (
    "你是企业知识库检索专家。给定用户问题和一组编号的文档片段，"
    "请按与问题的相关性从高到低排序。\n"
    "规则：\n"
    "1. 只输出排序后的编号 JSON 数组，例如 [3, 0, 7, 2, ...]，不要输出任何其他内容。\n"
    "2. 必须包含所有编号，每个编号只出现一次。\n"
    "3. 判断相关性时关注：片段是否直接回答问题的核心诉求（含具体数字、标准、流程等）。"
)


def _format_candidates(question: str, candidates: List[Dict]) -> str:
    """格式化候选分块为 LLM 输入"""
    lines = [f"用户问题：{question}", "", "文档片段列表："]
    for i, c in enumerate(candidates):
        content = (c.get("content") or "").strip()
        if len(content) > MAX_CHUNK_CHARS:
            content = content[:MAX_CHUNK_CHARS] + "…"
        source = c.get("document_name", "")
        chapter = c.get("chapter", "")
        meta = f"{source} - {chapter}" if chapter else source
        lines.append(f"[{i}] ({meta}) {content}")
    return "\n".join(lines)


def _parse_ranking(text: str, n: int) -> Optional[List[int]]:
    """解析 LLM 输出的排序编号列表，非法时返回 None"""
    # 提取所有数字 token
    numbers = [int(m) for m in re.findall(r"\d+", text)]
    valid = []
    seen = set()
    for num in numbers:
        if 0 <= num < n and num not in seen:
            valid.append(num)
            seen.add(num)
    # 补上 LLM 漏掉的编号（按原顺序追加在末尾）
    for i in range(n):
        if i not in seen:
            valid.append(i)
    return valid if valid else None


class LLMReranker:
    """LLM 重排序器"""

    def __init__(self, candidate_count: int = 20):
        self.llm = get_llm()
        self.candidate_count = candidate_count

    def rerank(self, question: str, candidates: List[Dict]) -> List[Dict]:
        """
        对候选分块按相关性重排

        参数:
            question: 用户问题
            candidates: 融合检索候选（按原分数降序）

        返回:
            重排后的候选列表（与原列表等长；LLM 调用失败时保持原顺序）
        """
        if len(candidates) <= 1:
            return candidates

        user_content = _format_candidates(question, candidates)
        messages = [
            {"role": "system", "content": RERANK_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        try:
            result = self.llm.chat(
                messages, temperature=0, max_tokens=200,
                model=settings.RERANK_MODEL or None,  # 轻量模型（如 qwen-turbo）可显著降低延迟
            )
            ranking = _parse_ranking(result.get("content", ""), len(candidates))
        except Exception as e:
            logger.warning(f"LLM 重排序失败，回退到原顺序: {e}")
            ranking = None

        if ranking is None:
            return candidates

        return [candidates[i] for i in ranking]


# --- 全局单例 ---
_reranker: Optional[LLMReranker] = None


def get_reranker() -> LLMReranker:
    """获取重排序器单例"""
    global _reranker
    if _reranker is None:
        _reranker = LLMReranker()
    return _reranker
