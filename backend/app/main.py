# ============================================================
# FastAPI 应用入口
# 组装路由、中间件、异常处理、生命周期管理
# ============================================================

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.exceptions import AppException
from app.db.sqlite import init_db, engine

# 导入所有模型确保注册到 SQLAlchemy Base 元数据
import app.models.user      # noqa: F401
import app.models.document  # noqa: F401
import app.models.chat      # noqa: F401
import app.models.ticket    # noqa: F401
import app.models.audit     # noqa: F401
import app.models.workflow  # noqa: F401
import app.models.attendance  # noqa: F401
import app.models.notification  # noqa: F401

from app.models.user import Role, User
from app.core.security import hash_password

# ==================== 应用生命周期 ====================


def _check_security_config():
    """
    启动前安全配置守卫：拒绝使用可被公开猜测的密钥启动。

    JWT_SECRET_KEY 为空或命中已知占位值时直接抛 RuntimeError，
    防止部署者复制 .env.example 后未修改密钥，导致攻击者可离线伪造
    超管身份的 JWT Token（密钥公开可见 + 默认管理员 ID=1 可猜）。
    """
    weak_jwt_secrets = {
        "jwt-secret-change-in-production",
        "jwt-dev-secret-2024",
        "change-this-to-a-random-secret-key",
    }
    if not settings.JWT_SECRET_KEY or settings.JWT_SECRET_KEY in weak_jwt_secrets:
        raise RuntimeError(
            "JWT_SECRET_KEY 未配置或仍为公开占位值，拒绝启动。"
            "请在 backend/.env 中设置强随机密钥（如 "
            "python -c \"import secrets; print(secrets.token_urlsafe(48))\" 生成）后重启。"
        )

    # 管理员初始密码守卫：拒绝使用 .env.example 占位值启动
    # （仅拦截占位值，不拦截短密码——避免误伤开发环境既有凭据）
    weak_admin_passwords = {
        "",  # 未配置
        "change-this-to-a-strong-password",  # .env.example 中的占位值
    }
    if settings.ADMIN_PASSWORD in weak_admin_passwords:
        raise RuntimeError(
            "ADMIN_PASSWORD 未配置或仍为 .env.example 占位值，拒绝启动。"
            "请在 backend/.env 中设置强密码后重启。"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时
    print(f"[启动] {settings.APP_NAME} v{settings.APP_VERSION}")

    # 安全配置守卫：JWT 密钥必须为强随机值，否则拒绝启动
    _check_security_config()

    print(f"[启动] 初始化数据库...")

    # 创建所有表
    init_db()

    # 初始化默认数据（角色 + 管理员）
    _init_default_data()

    print(f"[启动] 服务就绪，监听 {settings.HOST}:{settings.PORT}")
    yield
    # 关闭时
    print("[关闭] 正在关闭服务...")
    engine.dispose()


# ==================== 创建应用 ====================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ==================== CORS 中间件 ====================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 全局异常处理 ====================


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """处理自定义应用异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": exc.detail,
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """处理未捕获的通用异常"""
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "code": 5000,
            "message": "服务器内部错误，请稍后重试",
            "data": None,
        }
    )


# ==================== 注册路由 ====================

from app.api.v1 import auth, documents, chat, admin, tickets, security, workflow, workbench, contacts, attendance, notifications

app.include_router(auth.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(documents.admin_review_router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(tickets.router, prefix="/api/v1")
app.include_router(tickets.admin_router, prefix="/api/v1")
app.include_router(security.router, prefix="/api/v1")
app.include_router(workflow.router, prefix="/api/v1")
app.include_router(workbench.router, prefix="/api/v1")
app.include_router(contacts.router, prefix="/api/v1")
app.include_router(attendance.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")

# 挂载静态文件目录（头像等）
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(os.path.join(static_dir, "avatars"), exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ==================== 健康检查 ====================

@app.get("/api/health", tags=["系统"])
def health_check():
    """服务健康检查"""
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


# ==================== 辅助函数 ====================

def _init_default_data():
    """
    初始化默认角色和管理员账号
    只在数据库为空时执行
    """
    from sqlalchemy.orm import Session
    from app.db.sqlite import SessionLocal

    db = SessionLocal()
    try:
        # 已初始化的库：执行幂等的权限默认值升级（见 _upgrade_role_permissions）
        if db.query(Role).count() > 0:
            _upgrade_role_permissions(db)
            return

        # 创建预置角色
        roles = [
            Role(name="超级管理员", code="super_admin",
                 description="拥有系统全部权限",
                 permissions=["*"]),
            Role(name="知识库管理员", code="knowledge_admin",
                 description="管理文档和知识库内容",
                 permissions=["documents:*", "categories:*", "logs:read", "stats:read", "chat:ask"]),
            Role(name="总经理", code="boss",
                 description="审批超阈值单据，查看全局业务统计",
                 permissions=["chat:ask", "documents:read", "stats:read",
                              "leaves:read", "expenses:read",
                              "approvals:read", "approvals:approve"]),
            Role(name="部门管理员", code="dept_admin",
                 description="部门经理：审批本部门单据，管理部门文档和问答统计",
                 permissions=["documents:read", "stats:read", "chat:ask",
                              "leaves:read", "expenses:read",
                              "approvals:read", "approvals:approve"]),
            Role(name="普通员工", code="employee",
                 description="制度问答与办公流程自助办理",
                 permissions=["chat:ask", "documents:read",
                              "leaves:read", "leaves:submit",
                              "expenses:read", "expenses:submit"]),
        ]
        db.add_all(roles)
        db.flush()

        # 创建默认管理员
        # 强密码由环境变量提供（无默认值），为空则拒绝创建，避免弱密码入库
        if not settings.ADMIN_PASSWORD:
            raise RuntimeError(
                "未配置 ADMIN_PASSWORD，拒绝创建默认管理员。"
                "请在 backend/.env 中设置 ADMIN_PASSWORD 为强密码后重启。"
            )
        admin_role = db.query(Role).filter(Role.code == "super_admin").first()
        admin = User(
            username=settings.ADMIN_USERNAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            email=settings.ADMIN_EMAIL,
            real_name="系统管理员",
            role_id=admin_role.id,
        )
        db.add(admin)
        db.commit()
        # 不在日志中输出密码明文
        print(f"[启动] 已创建默认管理员: {settings.ADMIN_USERNAME}（密码来自环境变量 ADMIN_PASSWORD）")

    finally:
        db.close()


def _upgrade_role_permissions(db):
    """
    将"从未被改动的预置角色默认权限集"升级到新版本（幂等，每次启动执行）。

    背景：权限点此前未被接口层强制校验（角色管理页修改后不生效），
    旧默认集缺少 chat:ask，导致强制校验后 knowledge_admin/dept_admin 无法问答。
    仅当角色权限列表与旧默认完全一致（即管理员从未自定义过）时才升级，
    管理员自定义过的权限不受影响。

    OA 重构升级：为员工/部门管理员补充请假报销审批权限点，
    并确保"总经理（boss）"角色存在（新角色，直接创建，不影响自定义）。
    """
    # 各角色的 OA 扩展权限集：采用增量合并（并集）策略——
    # 只补充缺失的权限点，绝不删减管理员自定义过的权限（幂等）。
    oa_extra_perms = {
        "knowledge_admin": ["leaves:read", "expenses:read"],
        "dept_admin": ["leaves:read", "expenses:read",
                       "approvals:read", "approvals:approve"],
        "employee": ["documents:read",
                     "leaves:read", "leaves:submit",
                     "expenses:read", "expenses:submit"],
    }
    changed = False
    for code, extra in oa_extra_perms.items():
        role = db.query(Role).filter(Role.code == code).first()
        if role:
            current = list(role.permissions or [])
            merged = list(dict.fromkeys(current + extra))  # 并集去重，保持原有顺序
            if merged != current:
                role.permissions = merged
                changed = True

    # 确保总经理（boss）角色存在（OA 审批终审节点）
    boss = db.query(Role).filter(Role.code == "boss").first()
    if boss is None:
        db.add(Role(
            name="总经理", code="boss",
            description="审批超阈值单据，查看全局业务统计",
            permissions=["chat:ask", "documents:read", "stats:read",
                         "leaves:read", "expenses:read",
                         "approvals:read", "approvals:approve"],
        ))
        changed = True

    if changed:
        db.commit()
        print("[启动] 已升级预置角色默认权限（OA 审批权限点 + 总经理角色）")
