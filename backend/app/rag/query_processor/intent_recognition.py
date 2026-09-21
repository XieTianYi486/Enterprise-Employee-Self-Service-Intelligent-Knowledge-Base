# ============================================================
# 意图识别
# 分类用户问题，路由到不同的处理策略
# ============================================================

from typing import Literal

IntentType = Literal["greeting", "qa", "navigation", "rejected"]


# 简单的关键词规则匹配（无需 LLM 调用，快速路由）
GREETING_PATTERNS = [
    "你好", "您好", "hi", "hello", "早上好", "下午好", "晚上好",
    "谢谢", "感谢", "再见", "bye",
]

NAVIGATION_PATTERNS = [
    "找一下", "有哪些文档", "帮我找", "查一下文档",
    "在哪里", "怎么下载", "帮我查",
]

REJECTED_PATTERNS = [
    "攻击", "注入", "ignore", "system prompt", "忽略",
    "之前的指令", "重新开始",
]


def detect_intent(question: str) -> IntentType:
    """
    识别用户问题的意图

    返回:
        "greeting"   - 闲聊/问候 → 直接回复，不走 RAG
        "qa"         - 制度问答 → 完整 RAG 流程
        "navigation" - 文档导航 → 返回相关文档列表
        "rejected"   - 违规内容 → 直接拒答
    """
    question_lower = question.strip().lower()

    # 检测违规意图
    for pattern in REJECTED_PATTERNS:
        if pattern.lower() in question_lower:
            return "rejected"

    # 检测闲聊意图
    for pattern in GREETING_PATTERNS:
        if pattern.lower() in question_lower:
            # 短问题 + 问候词 = 闲聊
            if len(question) < 15:
                return "greeting"

    # 检测文档导航意图
    for pattern in NAVIGATION_PATTERNS:
        if pattern.lower() in question_lower:
            return "navigation"

    # 默认：制度问答
    return "qa"


def get_greeting_response(question: str) -> str:
    """闲聊回复"""
    if any(w in question for w in ["你好", "您好", "hi", "hello"]):
        return "您好！我是企业制度知识库助手，请问有什么可以帮助您的？"
    if any(w in question for w in ["谢谢", "感谢"]):
        return "不客气！如果还有其他问题，随时可以问我。"
    return "您好！请问有什么关于公司制度的问题需要我解答吗？"


def get_rejected_response() -> str:
    """违规拒答"""
    return "抱歉，我无法处理这个问题。如有制度相关的疑问，请重新提问。"
