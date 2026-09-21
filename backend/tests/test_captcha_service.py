# ============================================================
# 验证码服务单元测试：生成、校验、过期（内存缓存，无需数据库）
# ============================================================

import re
import time

from app.db.cache import cache
from app.services.captcha_service import CaptchaService


def _answer_of(challenge: str) -> int:
    """从算式题面解析正确答案，如 '3 + 5 = ?' -> 8"""
    nums = [int(n) for n in re.findall(r"\d+", challenge)]
    return sum(nums)


class TestCaptcha:
    def test_generate_and_verify(self):
        data = CaptchaService.generate()
        assert data["token"]
        assert "=" in data["challenge"]
        assert CaptchaService.verify(data["token"], _answer_of(data["challenge"]))

    def test_verify_wrong_answer(self):
        data = CaptchaService.generate()
        wrong = _answer_of(data["challenge"]) + 1
        assert not CaptchaService.verify(data["token"], wrong)

    def test_verify_invalid_token(self):
        assert not CaptchaService.verify("nonexistent_token", 3)
        assert not CaptchaService.verify("", 3)

    def test_verify_non_numeric_code(self):
        data = CaptchaService.generate()
        assert not CaptchaService.verify(data["token"], "abc")

    def test_verify_expired(self):
        """把缓存中的过期时间改到过去，模拟验证码过期"""
        data = CaptchaService.generate()
        answer = _answer_of(data["challenge"])
        key = CaptchaService._key(data["token"])
        cache.set_to_memory(key, {"answer": answer, "exp_at": time.time() - 10})
        assert not CaptchaService.verify(data["token"], answer)
