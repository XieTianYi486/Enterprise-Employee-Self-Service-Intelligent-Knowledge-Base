# ============================================================
# 查询改写（Query Rewrite）
# 使用 LLM 对用户问题进行优化，提升检索效果
# 旧项目无此能力，新项目核心差异化特性之一
# ============================================================

import json
from typing import List, Optional

from app.rag.llm.dashscope_llm import get_llm
from app.core.config import settings


QUERY_REWRITE_PROMPT = """你是一个查询优化助手。你的任务是将用户关于公司制度的问题改写为更适合检索的查询语句。

【改写规则】
1. 将口语化表达改写为正式的制度文档用语
2. 补全指代不明的缩写（如"HR"→"人力资源部门"）
3. 提取核心关键词和同义词
4. 生成 2-3 个语义等价但表述不同的查询变体

【输出格式】
请只输出 JSON 格式，不要包含其他内容：
{{
  "rewritten": "改写后的主要查询",
  "variants": ["变体1", "变体2"],
  "keywords": ["关键词1", "关键词2", "关键词3"]
}}

【用户问题】
{question}
"""


class QueryRewriter:
    """
    查询改写器

    策略：
    1. 口语转书面语
    2. 上下文补全（结合多轮对话历史）
    3. 生成多个查询变体以提升召回率
    """

    def __init__(self):
        self.llm = get_llm()

    def rewrite(
        self,
        question: str,
        chat_history: Optional[List[dict]] = None,
    ) -> dict:
        """
        改写用户问题

        参数:
            question: 原始问题
            chat_history: 对话历史 [{"role": "user"|"assistant", "content": "..."}]

        返回:
            {
                "rewritten": "改写后的查询",
                "variants": ["变体1", "变体2"],
                "keywords": ["关键词1", ...]
            }
        """
        # 配置关闭改写时直接降级（省一次 LLM 调用，显著降低首字延迟）
        if not settings.QUERY_REWRITE_ENABLED:
            return {"rewritten": question, "variants": [], "keywords": []}

        # 构建带历史的 prompt
        prompt = QUERY_REWRITE_PROMPT.format(question=question)

        if chat_history and len(chat_history) > 0:
            # 注入对话历史，帮助指代消解
            history_text = ""
            for msg in chat_history[-4:]:  # 最近 2 轮对话
                role = "用户" if msg["role"] == "user" else "助手"
                history_text += f"{role}: {msg['content']}\n"
            prompt = prompt.replace(
                "【用户问题】",
                f"【对话历史】\n{history_text}\n\n【用户问题】"
            )

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=256,
                model=settings.REWRITE_MODEL or None,  # 轻量模型（如 qwen-turbo）可显著降低延迟
            )

            content = response["content"].strip()
            # 提取 JSON（可能包裹在代码块中）
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                if content.endswith("```"):
                    content = content[:-3]

            result = json.loads(content)
            return {
                "rewritten": result.get("rewritten", question),
                "variants": result.get("variants", [question]),
                "keywords": result.get("keywords", []),
            }

        except Exception:
            # 降级：原样返回
            return {
                "rewritten": question,
                "variants": [question],
                "keywords": [],
            }


# --- 全局单例 ---
_query_rewriter: Optional[QueryRewriter] = None


def get_query_rewriter() -> QueryRewriter:
    """获取查询改写器单例"""
    global _query_rewriter
    if _query_rewriter is None:
        _query_rewriter = QueryRewriter()
    return _query_rewriter
