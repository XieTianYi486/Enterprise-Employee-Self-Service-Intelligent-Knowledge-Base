# ============================================================
# SQLite 数据库连接管理（同步 SQLAlchemy）
# 与旧项目的 aiosqlite 异步方案区分开
# ============================================================

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from app.core.config import settings

# --- 创建引擎 ---
# SQLite 需要 check_same_thread=False 以支持多线程
connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args["check_same_thread"] = False
    # 写锁等待时间（秒）：并发写入时等待而不是立刻报 "database is locked"
    connect_args["timeout"] = 30

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,  # 开发环境打印 SQL
    pool_pre_ping=True,   # 连接前检测可用性
)

# --- SQLite 特定优化 ---
if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """启用 SQLite WAL 模式、外键约束、UTF-8 编码"""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA encoding='UTF-8';")
        cursor.close()
        # 确保文本以 UTF-8 正确处理
        dbapi_connection.text_factory = str

# --- 会话工厂 ---
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,  # 手动控制 flush
    expire_on_commit=False,  # commit 后不使对象过期，避免 detached instance 错误
)

# --- 声明式基类 ---
Base = declarative_base()


def get_db() -> Session:
    """
    FastAPI 依赖注入：获取数据库会话

    使用方式:
        @router.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()

    注意：请求结束时自动关闭会话，异常时自动回滚
    支持端点提前关闭 Session 的场景（如流式响应端点）
    """
    db = SessionLocal()
    try:
        yield db
        try:
            db.commit()  # 正常结束则提交（若 Session 已提前关闭则跳过）
        except Exception:
            pass  # Session 已被端点关闭，忽略提交错误
    except Exception:
        try:
            db.rollback()  # 异常则回滚
        except Exception:
            pass
        raise  # 必须重新抛出端点异常，否则 FastAPI 返回 500 且真实错误被吞掉
    finally:
        try:
            db.close()
        except Exception:
            pass  # Session 可能已关闭，忽略


def init_db():
    """
    初始化数据库：创建所有表，自动迁移新增列
    在应用启动时调用一次
    """
    Base.metadata.create_all(bind=engine)
    # 自动迁移：为已有表添加新列（SQLite ALTER TABLE 兼容）
    _migrate_add_columns(engine)


def _migrate_add_columns(engine):
    """自动为已有表添加缺失的列（无痛迁移）"""
    import sqlite3
    # 通过原始 SQLite 连接执行
    with engine.connect() as conn:
        # 获取 users 表已有列
        result = conn.exec_driver_sql("PRAGMA table_info(users)")
        existing_cols = {row[1] for row in result}
        migrations = [
            ("avatar_url", "TEXT"),
            ("position", "TEXT"),
            # 登录安全字段
            ("failed_attempts", "INTEGER DEFAULT 0"),
            ("locked_until", "DATETIME"),
            # OA 员工档案字段
            ("dept_id", "INTEGER"),
            ("gender", "TEXT"),
            ("entry_date", "DATE"),
        ]
        for col_name, col_type in migrations:
            if col_name not in existing_cols:
                sql = f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"
                conn.exec_driver_sql(sql)

        # 一次性数据回填：新引入 dept_id 外键后，
        # 按历史 department 字符串列匹配 departments.name 回填部门归属
        if "dept_id" not in existing_cols:
            conn.exec_driver_sql(
                "UPDATE users SET dept_id = ("
                "  SELECT id FROM departments WHERE departments.name = users.department"
                ") WHERE department IS NOT NULL AND department != ''"
            )

        # documents 表追加知识审核发布流字段
        doc_result = conn.exec_driver_sql("PRAGMA table_info(documents)")
        doc_cols = {row[1] for row in doc_result}
        doc_migrations = [
            ("review_status", "INTEGER DEFAULT 1"),
            ("reviewed_by", "INTEGER"),
            ("reviewed_at", "DATETIME"),
            ("review_comment", "TEXT"),
        ]
        added_review_col = False
        for col_name, col_type in doc_migrations:
            if col_name not in doc_cols:
                conn.exec_driver_sql(
                    f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}"
                )
                added_review_col = added_review_col or (col_name == "review_status")

        # 一次性的数据回填：新增 review_status 列后，把已有的"已发布(status=1)"文档
        # 置为"已通过(2)"，避免上线后存量知识全部变不可见
        if added_review_col:
            conn.exec_driver_sql(
                "UPDATE documents SET review_status = 2 WHERE status = 1"
            )

        conn.commit()
