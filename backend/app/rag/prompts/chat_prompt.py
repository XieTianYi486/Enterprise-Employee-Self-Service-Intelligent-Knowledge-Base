# ============================================================
# 聊天 Prompt 模板
# 包括：系统指令、上下文组装、Rerank 候选格式化
# ============================================================


SYSTEM_PROMPT_TEMPLATE = """你是一个企业内部制度知识库问答助手。你的任务是基于提供的参考资料，准确回答员工关于公司制度的问题。

【重要规则】
1. 只能基于【参考资料】中的内容回答问题，不要编造任何信息。
2. 如果参考资料中没有相关信息，或者信息不足以回答问题，请明确说"抱歉，知识库中未找到相关信息，建议您咨询 HR 部门或查看完整制度文档。"
3. 回答要准确、简洁、有条理，优先引用制度原文中的表述。
4. 如果参考资料中有多个相关条款，请整合后回答，并在末尾注明来源。
5. 涉及数字、日期、金额等精确信息时，务必与原文一致，不得自行修改。
6. 回答时使用中文，语气正式、专业、友好。

【参考资料】
{context}

【回答格式要求】
- 先给出明确的答案
- 如有需要，分点说明
- 最后以列表形式标注信息来源：[文档名称 - 章节 - 页码]
"""


def build_system_prompt(context_chunks: list) -> str:
    """
    根据检索到的上下文构建 System Prompt

    参数:
        context_chunks: 检索到的文档片段列表，每个包含 content, document_name, chapter, page

    返回:
        格式化后的 System Prompt 字符串
    """
    if not context_chunks:
        return SYSTEM_PROMPT_TEMPLATE.format(
            context="（知识库中暂无相关内容）"
        )

    # 组装上下文（按相关性排序）
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        doc_name = chunk.get("document_name", "未知文档")
        chapter = chunk.get("chapter", "")
        page = chunk.get("page", "")
        content = chunk.get("content", "")

        source_info = f"【来源 {i+1}】{doc_name}"
        if chapter:
            source_info += f" - {chapter}"
        if page:
            source_info += f" - 第{page}页"

        context_parts.append(f"{source_info}\n{content}")

    context_text = "\n\n---\n\n".join(context_parts)

    return SYSTEM_PROMPT_TEMPLATE.format(context=context_text)


def build_chat_messages(
    question: str,
    context_chunks: list,
    chat_history: list = None,
) -> list:
    """
    构建完整的聊天消息列表（system + history + user）

    参数:
        question: 用户当前问题
        context_chunks: 检索到的文档片段
        chat_history: 历史消息列表 [{"role": "user"|"assistant", "content": "..."}]

    返回:
        [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, ...]
    """
    messages = []

    # System Prompt
    system_content = build_system_prompt(context_chunks)
    messages.append({"role": "system", "content": system_content})

    # 历史对话（最近 N 轮）
    if chat_history:
        # 确保不超过上下文窗口
        recent_history = chat_history[-10:]  # 最近 10 条消息（5 轮对话）
        messages.extend(recent_history)

    # 当前问题
    messages.append({"role": "user", "content": question})

    return messages
