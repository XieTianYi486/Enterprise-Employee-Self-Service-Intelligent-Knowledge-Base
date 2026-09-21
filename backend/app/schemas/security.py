# ============================================================
# 安全合规相关 Pydantic Schema
# 敏感词管理接口的请求体校验
# ============================================================

from typing import Optional

from pydantic import BaseModel, Field


class SensitiveWordCreate(BaseModel):
    """新增敏感词请求"""
    word: str = Field(..., min_length=1, max_length=64, description="敏感词内容")
    category: str = Field(
        default="general", pattern="^(general|security|pii)$", max_length=32,
        description="分类：general/security/pii",
    )
    level: int = Field(default=2, ge=1, le=3, description="级别：1提示级/2拦截级/3高危级")
    action: str = Field(
        default="mask", pattern="^(mask|block)$",
        description="动作：mask=脱敏替换, block=拦截",
    )
    replacement: str = Field(default="***", max_length=64, description="脱敏替换文本")


class SensitiveWordUpdate(BaseModel):
    """更新敏感词请求（仅提交需要修改的字段）"""
    word: Optional[str] = Field(default=None, min_length=1, max_length=64, description="敏感词内容")
    category: Optional[str] = Field(
        default=None, pattern="^(general|security|pii)$", max_length=32,
        description="分类：general/security/pii",
    )
    level: Optional[int] = Field(default=None, ge=1, le=3, description="级别：1提示级/2拦截级/3高危级")
    action: Optional[str] = Field(
        default=None, pattern="^(mask|block)$",
        description="动作：mask=脱敏替换, block=拦截",
    )
    replacement: Optional[str] = Field(default=None, max_length=64, description="脱敏替换文本")
    enabled: Optional[int] = Field(default=None, ge=0, le=1, description="是否启用：0停用/1启用")
