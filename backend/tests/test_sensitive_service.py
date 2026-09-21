# ============================================================
# 敏感词服务单元测试：命中检测、脱敏、高危拦截（纯逻辑，无需数据库）
# ============================================================

from app.models.audit import SensitiveWord
from app.services.sensitive_service import SensitiveService


def _word(text, level=2, action="mask", replacement="***", enabled=1):
    return SensitiveWord(
        word=text, level=level, action=action,
        replacement=replacement, enabled=enabled,
    )


class TestScanText:
    """敏感词命中检测"""

    def test_hits_with_count(self):
        words = [_word("机密文件"), _word("泄露")]
        text = "请不要查看机密文件，防止机密文件泄露。"
        hits = SensitiveService.scan_text(text, words)
        by_word = {h["word"]: h["count"] for h in hits}
        assert by_word == {"机密文件": 2, "泄露": 1}

    def test_no_hit(self):
        hits = SensitiveService.scan_text("普通的年假申请问题", [_word("机密")])
        assert hits == []

    def test_empty_word_skipped(self):
        hits = SensitiveService.scan_text("正常文本", [_word("")])
        assert hits == []


class TestMaskText:
    """回答脱敏"""

    def test_mask_replaces_word(self):
        words = [_word("秘密", replacement="[已脱敏]")]
        masked, hits = SensitiveService.mask_text("这是秘密项目", words)
        assert masked == "这是[已脱敏]项目"
        assert len(hits) == 1

    def test_mask_default_replacement(self):
        words = [_word("机密")]
        masked, _ = SensitiveService.mask_text("机密内容", words)
        assert masked == "***内容"


class TestContainsBlockWord:
    """高危词拒答拦截"""

    def test_level3_triggers(self):
        assert SensitiveService.contains_block_word(
            "讨论攻击方案", [_word("攻击", level=3)])

    def test_action_block_triggers(self):
        assert SensitiveService.contains_block_word(
            "这里有关键词", [_word("关键词", action="block")])

    def test_plain_mask_word_does_not_trigger(self):
        """普通脱敏词（level=2 + mask）不触发拒答拦截"""
        assert not SensitiveService.contains_block_word(
            "提到秘密一词", [_word("秘密")])

    def test_empty_text_safe(self):
        assert not SensitiveService.contains_block_word(
            "", [_word("秘密", level=3)])

    def test_disabled_word_ignored_by_caller(self):
        """enabled=0 的词由 get_enabled_words 过滤，纯逻辑层不关心启用状态"""
        assert SensitiveService.contains_block_word(
            "攻击内容", [_word("攻击", level=3, enabled=0)])
