# ============================================================
# 百炼 DashScope LLM 封装
# 使用 OpenAI 兼容模式调用 qwen-plus/qwen-max
# 支持同步和流式两种输出方式
# ============================================================

import json
import time
from typing import AsyncGenerator, Dict, List, Optional

from openai import OpenAI

from app.core.config import settings
from app.core.exceptions import LLMException


class BailianLLM:
    """
    百炼大模型调用封装

    使用 OpenAI 兼容接口（兼容性最好，支持流式输出）
    模型: qwen-plus（默认）
    """

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

        if not self.api_key:
            raise LLMException("未配置 DASHSCOPE_API_KEY")

        # 使用 OpenAI 兼容客户端
        base_url = settings.DASHSCOPE_OPENAI_BASE_URL or \
            "https://dashscope.aliyuncs.com/compatible-mode/v1"

        self._client = OpenAI(
            api_key=self.api_key,
            base_url=base_url,
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> Dict:
        """
        同步对话（非流式）

        参数:
            messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
            temperature: 生成温度
            max_tokens: 最大 token 数
            model: 模型覆盖（轻量任务如查询改写/重排序可传更快的模型）

        返回:
            {"content": "回答文本", "usage": {"prompt_tokens": ..., "completion_tokens": ...}}
        """
        try:
            response = self._client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                stream=False,
            )

            choice = response.choices[0]
            return {
                "content": choice.message.content or "",
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
            }

        except Exception as e:
            raise LLMException(f"LLM 调用失败: {str(e)}")

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式对话（返回 token 生成器）

        使用方式:
            async for token in llm.chat_stream(messages):
                yield f"data: {json.dumps({'token': token})}\n\n"
        """
        try:
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )

            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content

        except Exception as e:
            raise LLMException(f"LLM 流式调用失败: {str(e)}")


# --- 全局单例 ---
_llm_instance: Optional[BailianLLM] = None


def get_llm() -> BailianLLM:
    """获取 LLM 客户端单例"""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = BailianLLM()
    return _llm_instance
