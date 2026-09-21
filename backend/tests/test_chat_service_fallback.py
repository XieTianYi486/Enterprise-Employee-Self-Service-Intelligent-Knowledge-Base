# ============================================================
# 问答服务降级能力单元测试
# 覆盖：无 LLM 检索直出格式化、流程跳转建议规则
# ============================================================

from app.services.chat_service import ChatService


class TestFallbackAnswer:
    """LLM 不可用时检索直出（大模型是增强而非单点故障）"""

    def test_fallback_with_chunks_formats_sources(self):
        chunks = [
            {
                "document_name": "考勤管理制度",
                "chapter": "三",
                "page": 12,
                "content": "员工请假须提前一天在系统提交申请。" * 5,
            },
            {
                "document_name": "员工手册",
                "chapter": None,
                "page": None,
                "content": "年假按工龄核定。",
            },
        ]
        answer = ChatService._build_fallback_answer("请假规定", chunks)
        # 包含降级提示、文档名、章节页码、原文片段
        assert "智能生成服务暂不可用" in answer
        assert "《考勤管理制度》" in answer
        assert "第 三章" in answer or "第三章" in answer
        assert "（第12页）" in answer
        assert "《员工手册》" in answer

    def test_fallback_without_chunks_returns_guidance(self):
        answer = ChatService._build_fallback_answer("无关问题", [])
        assert "未找到相关信息" in answer


class TestSuggestedActions:
    """流程跳转建议：按关键词规则匹配（不依赖 LLM）"""

    def test_leave_keywords_suggest_leave(self):
        actions = ChatService._suggest_actions("我想请两天年假")
        assert {"type": "leave", "label": "去请假"} in actions

    def test_expense_keywords_suggest_expense(self):
        actions = ChatService._suggest_actions("差旅费怎么报销？")
        assert {"type": "expense", "label": "去报销"} in actions

    def test_ticket_keywords_suggest_ticket(self):
        actions = ChatService._suggest_actions("我要投诉食堂")
        assert {"type": "ticket", "label": "提交工单"} in actions

    def test_mixed_keywords_limited_to_two(self):
        actions = ChatService._suggest_actions("请假的费用能报销吗")
        assert len(actions) <= 2

    def test_no_keyword_returns_empty(self):
        assert ChatService._suggest_actions("今天天气怎么样") == []
