# ============================================================
# 认证相关 Pydantic Schema
# ============================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, EmailStr


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")
    captcha_token: Optional[str] = Field(default=None, description="验证码 Token")
    captcha_code: Optional[str] = Field(default=None, description="验证码答案")


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    email: Optional[str] = Field(default=None, max_length=128, description="邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="密码（6-128字符）")
    real_name: Optional[str] = Field(default=None, max_length=64, description="真实姓名")
    dept_id: Optional[int] = Field(default=None, description="所属部门ID")
    captcha_token: Optional[str] = Field(default=None, description="验证码 Token")
    captcha_code: Optional[str] = Field(default=None, description="验证码答案")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")


class TokenResponse(BaseModel):
    """Token 响应"""
    access_token: str = Field(..., description="JWT Token")
    token_type: str = Field(default="bearer", description="Token 类型")


class UserInfo(BaseModel):
    """用户信息（脱敏，不含密码）"""
    id: int
    username: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None  # 部门显示名（由 dept 关系填充）
    dept_id: Optional[int] = None
    gender: Optional[str] = None
    entry_date: Optional[datetime] = None
    role_id: int
    role_name: Optional[str] = None  # 角色名称（JOIN 查询填充）
    permissions: Optional[list] = None  # 角色权限点列表（前端导航/按钮显隐用）
    status: int
    created_at: datetime

    class Config:
        from_attributes = True  # 允许从 ORM 对象构建


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class UpdateProfileRequest(BaseModel):
    """
    更新个人资料请求

    安全约束：不含 dept_id——部门归属变动只能由超级管理员
    通过 /admin/users/{id}/department 接口操作，防止部门管理员
    自助改部门后越权审批他部门单据。
    """
    real_name: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=32)
    position: Optional[str] = Field(default=None, max_length=128)
    gender: Optional[str] = Field(default=None, description="性别（男/女）")
    entry_date: Optional[str] = Field(default=None, description="入职日期 yyyy-MM-dd")
