# ============================================================
# 自定义异常类
# 统一的业务异常体系，配合全局异常处理器使用
# ============================================================

from typing import Any, Optional


class AppException(Exception):
    """应用基础异常"""

    def __init__(
        self,
        message: str = "服务器内部错误",
        code: int = 5000,
        status_code: int = 500,
        detail: Optional[Any] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)


# ==================== 认证异常 ====================

class AuthenticationException(AppException):
    """认证失败异常（Token 无效、过期等）"""

    def __init__(self, message: str = "认证失败，请重新登录"):
        super().__init__(message=message, code=2001, status_code=401)


class PermissionDeniedException(AppException):
    """权限不足异常"""

    def __init__(self, message: str = "权限不足，无法执行此操作"):
        super().__init__(message=message, code=2002, status_code=403)


class TokenExpiredException(AuthenticationException):
    """Token 过期"""

    def __init__(self):
        super().__init__(message="登录已过期，请重新登录")


class AccountLockedException(AppException):
    """账号已锁定（连续登录失败）"""

    def __init__(self, message: str = "账号已锁定，请稍后重试"):
        super().__init__(message=message, code=2003, status_code=403)


# ==================== 业务异常 ====================

class NotFoundException(AppException):
    """资源未找到"""

    def __init__(self, message: str = "请求的资源不存在"):
        super().__init__(message=message, code=3001, status_code=404)


class DuplicateException(AppException):
    """资源冲突（如用户名重复）"""

    def __init__(self, message: str = "资源已存在"):
        super().__init__(message=message, code=3002, status_code=409)


class ValidationException(AppException):
    """业务校验失败"""

    def __init__(self, message: str = "数据校验失败"):
        super().__init__(message=message, code=1001, status_code=400)


# ==================== RAG 相关异常 ====================

class DocumentProcessException(AppException):
    """文档处理失败"""

    def __init__(self, message: str = "文档处理失败"):
        super().__init__(message=message, code=3003, status_code=500)


class EmbeddingException(AppException):
    """向量化失败"""

    def __init__(self, message: str = "文本向量化失败"):
        super().__init__(message=message, code=4001, status_code=500)


class LLMException(AppException):
    """LLM 调用失败"""

    def __init__(self, message: str = "AI 服务调用失败，请稍后重试"):
        super().__init__(message=message, code=4002, status_code=500)


class RetrievalException(AppException):
    """检索失败"""

    def __init__(self, message: str = "知识库检索失败"):
        super().__init__(message=message, code=4003, status_code=500)
