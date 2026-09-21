# ============================================================
# pytest 全局配置
# 关键：在导入任何 app 模块之前把 DATABASE_URL 指向独立测试库，
#       确保测试绝不触碰开发/生产数据库
# ============================================================

import os
import sys
from pathlib import Path

# 1) backend 目录加入 sys.path（保证 import app 可用）
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 2) 隔离测试数据库（必须在 import app.* 之前设置）
TEST_DATA_DIR = BACKEND_DIR / "tests" / ".tmp_test"
os.makedirs(TEST_DATA_DIR, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATA_DIR / 'test.db'}"

# 每次运行删除上次的测试库文件（用例内提交的数据会持久化，不能跨运行残留）
for _suffix in ("", "-wal", "-shm"):
    _f = Path(str(TEST_DATA_DIR / "test.db") + _suffix)
    if _f.exists():
        _f.unlink()

import pytest  # noqa: E402

# 3) 先导入全部模型注册到 Base.metadata，再初始化测试库表结构
import app.models.user  # noqa: E402, F401
import app.models.document  # noqa: E402, F401
import app.models.chat  # noqa: E402, F401
import app.models.ticket  # noqa: E402, F401
import app.models.audit  # noqa: E402, F401
import app.models.workflow  # noqa: E402, F401

from app.db.sqlite import init_db, engine, SessionLocal  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_test_db():
    """会话级夹具：创建全部表结构；测试结束后释放引擎"""
    init_db()
    yield
    engine.dispose()


@pytest.fixture()
def db():
    """每个测试独立的数据库会话，测试结束回滚，用例之间互不污染"""
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def roles(db):
    """预置五个 RBAC 角色（含 OA 总经理角色），返回 {code: Role}"""
    from app.models.user import Role

    role_map = {r.code: r for r in db.query(Role).all()}
    defaults = [
        ("超级管理员", "super_admin"),
        ("知识库管理员", "knowledge_admin"),
        ("总经理", "boss"),
        ("部门管理员", "dept_admin"),
        ("普通员工", "employee"),
    ]
    for name, code in defaults:
        if code not in role_map:
            role = Role(name=name, code=code, permissions=[])
            db.add(role)
            role_map[code] = role
    db.commit()
    return role_map


@pytest.fixture()
def employee_user(db, roles):
    """普通员工测试用户（密码 test123456，状态正常）
    用户名带随机后缀：用例内提交的数据会持久化，避免跨用例唯一键冲突
    """
    import uuid

    from app.core.security import hash_password
    from app.models.user import User

    user = User(
        username=f"tester_{uuid.uuid4().hex[:8]}",
        password_hash=hash_password("test123456"),
        email=f"tester_{uuid.uuid4().hex[:8]}@company.com",
        role_id=roles["employee"].id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
