# ============================================================
# 验证码服务（算式验证码）
# 免图形依赖，生成"a+b=?"算式，token 存储于内存缓存，带有效期
# ============================================================

import random
import time
import uuid

from app.core.config import settings
from app.db.cache import cache


class CaptchaService:
    """算术验证码（登录安全）"""

    @staticmethod
    def _key(token: str) -> str:
        return f"captcha:{token}"

    @staticmethod
    def generate() -> dict:
        """生成一道算术题，返回 {token, challenge}"""
        a = random.randint(1, 20)
        b = random.randint(1, 20)
        answer = a + b
        token = uuid.uuid4().hex[:20]
        exp_at = time.time() + settings.CAPTCHA_TTL_SECONDS
        cache.set_to_memory(CaptchaService._key(token), {
            "answer": answer, "exp_at": exp_at,
        })
        return {
            "token": token,
            "challenge": f"{a} + {b} = ?",
        }

    @staticmethod
    def verify(token: str, code) -> bool:
        """
        校验验证码。

        说明：算式验证码不做一次性消费（避免误输入造成体验割裂），
        通过后由登录失败锁定机制兜底防止暴力破解。
        """
        if not token:
            return False
        try:
            code_int = int(str(code).strip())
        except (TypeError, ValueError):
            return False
        data = cache.get_from_memory(CaptchaService._key(token))
        if not data:
            return False
        if data.get("exp_at", 0) < time.time():
            return False
        return code_int == data.get("answer")