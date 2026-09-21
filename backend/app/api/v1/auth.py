# ============================================================
# 认证接口
# POST /api/v1/auth/login
# POST /api/v1/auth/register
# GET /api/v1/auth/me
# POST /api/v1/auth/change-password
# ============================================================

from fastapi import APIRouter, Depends, File, Form, UploadFile, Request
from sqlalchemy.orm import Session

from app.db.sqlite import get_db
from app.api.deps import get_current_active_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest, RegisterRequest, ChangePasswordRequest, UpdateProfileRequest,
    TokenResponse, UserInfo, LoginResponse,
)
from app.schemas.common import APIResponse
from app.services.auth_service import AuthService
from app.services.captcha_service import CaptchaService
from app.services.audit_service import get_client_info
from app.core.config import settings
from app.core.exceptions import ValidationException

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=APIResponse, summary="用户注册")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """新用户注册（默认角色：普通员工）"""
    # 验证码校验（启用时必填），防止批量注册账号消耗问答 LLM 资源
    if settings.CAPTCHA_ENABLED:
        if not CaptchaService.verify(request.captcha_token, request.captcha_code):
            raise ValidationException("验证码错误或已过期，请重试")

    user = AuthService.register(db, request)
    return APIResponse(
        code=0,
        message="注册成功",
        data={"user_id": user.id, "username": user.username}
    )


@router.get("/captcha", response_model=APIResponse, summary="获取验证码")
def get_captcha():
    """获取登录算式验证码（返回 token 与算式文本）"""
    data = CaptchaService.generate()
    return APIResponse(
        code=0, message="success",
        data={"token": data["token"], "challenge": data["challenge"]}
    )


@router.post("/login", response_model=APIResponse, summary="用户登录")
def login(request: LoginRequest, request_ctx: Request, db: Session = Depends(get_db)):
    """用户登录，返回 JWT Token"""
    ip, ua = get_client_info(request_ctx)

    # 验证码校验（启用时必填）
    if settings.CAPTCHA_ENABLED:
        if not CaptchaService.verify(request.captcha_token, request.captcha_code):
            raise ValidationException("验证码错误或已过期，请重试")

    token, user = AuthService.login(
        db, request.username, request.password, ip=ip, user_agent=ua
    )
    user_info = AuthService.get_user_info(user)
    return APIResponse(
        code=0,
        message="登录成功",
        data={
            "access_token": token,
            "token_type": "bearer",
            "user": user_info,
        }
    )


@router.get("/sso/status", response_model=APIResponse, summary="SSO 接入状态")
def get_sso_status():
    """返回企业 SSO 的接入状态与配置信息（用于前端渲染 SSO 登录入口）"""
    return APIResponse(
        code=0,
        message="success",
        data={
            "enabled": settings.SSO_ENABLED,
            "provider": settings.SSO_PROVIDER,
            "server_url": settings.SSO_SERVER_URL,
            "app_id": settings.SSO_APP_ID,
        }
    )


@router.post("/sso/callback", response_model=APIResponse, summary="SSO 回调（预留）")
def sso_callback(db: Session = Depends(get_db)):
    """
    企业 SSO 单点登录回调（预留接口）。

    对接流程说明（请按所选 Provider 补充签名校验与用户映射逻辑）：
    1. OAuth2/SAML 回调携带授权码或断言；
    2. 前端 / 网关到 SSO_SERVER_URL 换取用户信息；
    3. 根据 SSO 唯一标识匹配/创建本地 User 并签发 JWT。

    当前未配置 SSO（SSO_ENABLED=False），直接返回未启用提示。
    """
    if not settings.SSO_ENABLED:
        return APIResponse(code=3001, message="SSO 尚未启用，请先在环境变量中配置")
    return APIResponse(
        code=0, message="SSO 集成占位接口",
        data={"provider": settings.SSO_PROVIDER, "note": "请在此实现第三方回调"}
    )


@router.get("/me", response_model=APIResponse, summary="获取当前用户信息")
def get_me(
    current_user: User = Depends(get_current_active_user),
):
    """获取当前登录用户的详细信息"""
    return APIResponse(
        code=0,
        message="success",
        data=AuthService.get_user_info(current_user)
    )


@router.post("/change-password", response_model=APIResponse, summary="修改密码")
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """修改当前用户的登录密码"""
    AuthService.change_password(
        db, current_user.id, request.old_password, request.new_password
    )
    return APIResponse(code=0, message="密码修改成功")


@router.put("/profile", response_model=APIResponse, summary="更新个人资料")
def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """更新当前用户的个人信息（姓名/邮箱/手机/职位/部门）"""
    # get_current_user 返回的是 detached 对象，直接修改不会落库；
    # 必须在当前 db 会话中重新查询后再更新（同 change_password 的处理方式）
    user = db.query(User).filter(User.id == current_user.id).first()
    if user is None:
        raise ValidationException("用户不存在")

    if request.real_name is not None:
        user.real_name = request.real_name
    if request.email is not None:
        user.email = request.email
    if request.phone is not None:
        user.phone = request.phone
    if request.position is not None:
        user.position = request.position
    if request.gender is not None:
        user.gender = request.gender
    if request.entry_date is not None:
        from datetime import datetime as _dt
        try:
            user.entry_date = _dt.strptime(request.entry_date, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationException("入职日期格式应为 yyyy-MM-dd")
    db.flush()
    return APIResponse(
        code=0, message="更新成功",
        data=AuthService.get_user_info(user)
    )


import os
import uuid
import shutil

# AVATAR_DIR 对齐 main.py 的 StaticFiles 挂载路径：backend/app/static/avatars/
AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)


@router.post("/avatar", response_model=APIResponse, summary="上传头像")
def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """上传用户头像（支持 jpg/png/gif/webp，最大 2MB）"""
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "jpg"
    if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
        return APIResponse(code=3002, message="仅支持 jpg/png/gif/webp 格式")

    if file.size and file.size > 2 * 1024 * 1024:
        return APIResponse(code=3002, message="头像大小不能超过 2MB")

    # 删除旧头像文件
    if current_user.avatar_url:
        old_path = os.path.join(AVATAR_DIR, os.path.basename(current_user.avatar_url))
        if os.path.exists(old_path):
            os.remove(old_path)

    # 保存新头像（seek(0) 必须，UploadFile 文件指针在末尾）
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(AVATAR_DIR, filename)
    file.file.seek(0)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 在当前 db 会话中重新查询用户后更新，确保 avatar_url 真实落库
    # （直接修改 detached 的 current_user 不会产生 UPDATE SQL）
    user = db.query(User).filter(User.id == current_user.id).first()
    if user is None:
        os.remove(filepath)  # 用户已不存在时清理刚写入的文件
        raise ValidationException("用户不存在")
    user.avatar_url = f"/static/avatars/{filename}"
    db.flush()

    return APIResponse(
        code=0, message="头像上传成功",
        data={"avatar_url": user.avatar_url}
    )
