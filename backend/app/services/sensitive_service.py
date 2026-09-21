# ============================================================
# 敏感词服务
# 提供：敏感词管理、文本脱敏、命中检测与审计
# ============================================================

import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit import SensitiveWord
from app.services.audit_service import add_audit_log

logger = logging.getLogger(__name__)


class SensitiveService:
    """敏感词过滤与脱敏业务逻辑"""

    # ----------------------------------------------------------
    # 敏感词 CRUD
    # ----------------------------------------------------------

    @staticmethod
    def list_words(db: Session, keyword: Optional[str] = None,
                   enabled: Optional[int] = None,
                   page: int = 1, page_size: int = 20):
        from app.schemas.common import PaginatedData
        query = db.query(SensitiveWord)
        if keyword:
            query = query.filter(SensitiveWord.word.contains(keyword))
        if enabled is not None:
            query = query.filter(SensitiveWord.enabled == enabled)
        total = query.count()
        items = query.order_by(SensitiveWord.id.desc()) \
            .offset((page - 1) * page_size).limit(page_size).all()
        return items, total

    @staticmethod
    def create_word(db: Session, word: str, level: int = 2,
                    action: str = "mask", replacement: str = "***",
                    category: str = "general") -> SensitiveWord:
        existing = db.query(SensitiveWord).filter(
            SensitiveWord.word == word).first()
        if existing:
            raise ValueError("敏感词已存在")
        item = SensitiveWord(
            word=word, level=level, action=action,
            replacement=replacement, category=category,
        )
        db.add(item)
        db.flush()
        return item

    @staticmethod
    def update_word(db: Session, word_id: int, **fields) -> SensitiveWord:
        item = db.query(SensitiveWord).filter(
            SensitiveWord.id == word_id).first()
        if not item:
            raise LookupError("敏感词不存在")
        for k in ("word", "level", "action", "replacement", "category", "enabled"):
            if fields.get(k) is not None:
                setattr(item, k, fields[k])
        db.flush()
        return item

    @staticmethod
    def delete_word(db: Session, word_id: int) -> None:
        item = db.query(SensitiveWord).filter(
            SensitiveWord.id == word_id).first()
        if not item:
            raise LookupError("敏感词不存在")
        db.delete(item)
        db.flush()

    # ----------------------------------------------------------
    # 启用词加载 + 过滤
    # ----------------------------------------------------------

    @staticmethod
    def get_enabled_words(db: Session) -> List[SensitiveWord]:
        if not settings.SENSITIVE_WORD_ENABLED:
            return []
        return db.query(SensitiveWord).filter(
            SensitiveWord.enabled == 1).all()

    @staticmethod
    def scan_text(text: str, words: List[SensitiveWord]) -> List[dict]:
        """
        检测文本中的敏感词命中。

        返回: [{"word": str, "count": int, "level": int, "action": str}, ...]
        """
        hits = []
        used = set()
        for w in words:
            if w.word in used or not w.word:
                continue
            used.add(w.word)
            cnt = text.count(w.word)
            if cnt > 0:
                hits.append({
                    "word": w.word, "count": cnt,
                    "level": w.level, "action": w.action,
                    "replacement": w.replacement,
                })
        return hits

    @staticmethod
    def mask_text(text: str, words: List[SensitiveWord]) -> Tuple[str, List[dict]]:
        """
        脱敏：将文本中的敏感词替换为 replacement。

        返回: (处理后的文本, 命中列表)
        """
        hits = SensitiveService.scan_text(text, words)
        masked = text
        for h in hits:
            repl = h.get("replacement") or "***"
            masked = masked.replace(h["word"], repl)
        return masked, hits

    @staticmethod
    def contains_block_word(text: str, words: List[SensitiveWord]) -> bool:
        """是否命中高危拦截词（level=3 或 action=block）"""
        for w in words:
            if w.level >= 3 or w.action == "block":
                if w.word and w.word in text:
                    return True
        return False

    # ----------------------------------------------------------
    # 回答脱敏 + 审计
    # ----------------------------------------------------------

    @staticmethod
    def mask_answer(answer: str, db: Session, user_id=None,
                    username=None, ip=None, user_agent=None) -> Tuple[str, List[dict]]:
        """
        对 AI 回答进行敏感词脱敏，并记录命中审计日志。

        返回: (脱敏后的回答, 命中列表)
        """
        words = SensitiveService.get_enabled_words(db)
        if not words or not answer:
            return answer, []
        masked, hits = SensitiveService.mask_text(answer, words)
        if hits:
            add_audit_log(
                db=db, module="sensitive", action="sensitive_hit",
                status="masked", user_id=user_id, username=username,
                target_type="chat", detail={"hits": hits},
                ip=ip, user_agent=user_agent,
            )
        return masked, hits