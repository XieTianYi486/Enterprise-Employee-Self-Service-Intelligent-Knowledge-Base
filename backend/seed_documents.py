# ============================================================
# 种子数据导入脚本
# 将 sample_docs 目录下的企业制度文档批量导入知识库
# 使用方法: cd backend && python seed_documents.py
# ============================================================

import os
import sys
import shutil
import uuid
from pathlib import Path
from datetime import date

# 将 backend 目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.orm import Session
from app.db.sqlite import SessionLocal, engine, Base
from app.models.document import Document, Category
from app.models.user import User
from app.tasks.document_tasks import _process_document_task


# ==================== 预定义分类 ====================

DEFAULT_CATEGORIES = [
    {"name": "人力资源", "parent_id": 0, "sort_order": 1,
     "description": "考勤、薪酬、绩效、招聘、培训等HR相关制度"},
    {"name": "行政管理", "parent_id": 0, "sort_order": 2,
     "description": "办公室、差旅、资产、印章、会议等行政制度"},
    {"name": "财务管理", "parent_id": 0, "sort_order": 3,
     "description": "预算、报销、资金、税务、审计等财务制度"},
    {"name": "信息技术", "parent_id": 0, "sort_order": 4,
     "description": "IT设备、网络、安全、数据、软件等IT制度"},
    {"name": "法务合规", "parent_id": 0, "sort_order": 5,
     "description": "合同、知识产权、保密、合规等法务制度"},
    {"name": "采购管理", "parent_id": 0, "sort_order": 6,
     "description": "供应商管理、采购流程、招标等采购制度"},
    {"name": "市场营销", "parent_id": 0, "sort_order": 7,
     "description": "市场活动、广告投放、品牌宣传、销售管理、客户服务"},
    # 子分类
    {"name": "考勤管理", "parent_id": 1, "sort_order": 1,
     "description": "工作时间、请假、加班、出差考勤"},
    {"name": "薪酬福利", "parent_id": 1, "sort_order": 2,
     "description": "薪酬结构、社保公积金、福利补贴"},
    {"name": "绩效晋升", "parent_id": 1, "sort_order": 3,
     "description": "绩效考核、晋升评审、奖惩管理"},
    {"name": "入职离职", "parent_id": 1, "sort_order": 4,
     "description": "劳动合同、入职手续、离职流程"},
    {"name": "差旅管理", "parent_id": 2, "sort_order": 1,
     "description": "出差审批、交通住宿、差旅报销"},
    {"name": "安全与保密", "parent_id": 4, "sort_order": 1,
     "description": "信息安全、数据保护、保密制度"},
    {"name": "IT设备管理", "parent_id": 4, "sort_order": 2,
     "description": "设备配置、使用规范、报修报废"},
    {"name": "合同管理", "parent_id": 5, "sort_order": 1,
     "description": "合同签订、审核、履行与归档"},
    {"name": "知识产权", "parent_id": 5, "sort_order": 2,
     "description": "专利、商标、软件著作权、开源合规"},
    {"name": "市场推广", "parent_id": 7, "sort_order": 1,
     "description": "市场活动、广告投放、品牌宣传"},
    {"name": "销售管理", "parent_id": 7, "sort_order": 2,
     "description": "销售线索、报价合同、业绩提成、商务合规"},
    {"name": "客户服务", "parent_id": 7, "sort_order": 3,
     "description": "服务响应、投诉处理、售后与满意度"},
]

# ==================== 种子文档清单 ====================

SEED_DOCUMENTS = [
    {
        "filename": "00_员工考勤管理制度_完整版.md",
        "title": "员工考勤管理制度",
        "category_id": None,  # 动态映射到"考勤管理"
        "category_name": "考勤管理",
        "tags": ["考勤", "请假", "加班", "出差", "工作时间"],
        "security_level": 1,  # 公开
    },
    {
        "filename": "01_员工手册.md",
        "title": "员工手册",
        "category_id": None,
        "category_name": "人力资源",
        "tags": ["员工手册", "入职", "薪酬福利", "行为规范", "离职"],
        "security_level": 1,
    },
    {
        "filename": "02_差旅费管理办法.md",
        "title": "差旅费管理办法",
        "category_id": None,
        "category_name": "差旅管理",
        "tags": ["差旅", "报销", "交通", "住宿", "出差"],
        "security_level": 1,
    },
    {
        "filename": "03_信息安全与保密制度.md",
        "title": "信息安全与保密制度",
        "category_id": None,
        "category_name": "安全与保密",
        "tags": ["信息安全", "保密", "数据保护", "网络安全", "合规"],
        "security_level": 2,  # 内部
    },
    {
        "filename": "04_IT设备使用规范.md",
        "title": "IT设备使用规范",
        "category_id": None,
        "category_name": "IT设备管理",
        "tags": ["IT设备", "电脑", "软件", "网络", "技术支持"],
        "security_level": 1,
    },
    {
        "filename": "05_财务管理制度.md",
        "title": "财务管理制度",
        "category_id": None,
        "category_name": "财务管理",
        "tags": ["财务", "预算", "资金", "报销", "税务", "审计"],
        "security_level": 2,
    },
    {
        "filename": "06_劳动合同与入职管理制度.md",
        "title": "劳动合同与入职管理制度",
        "category_id": None,
        "category_name": "入职离职",
        "tags": ["劳动合同", "入职", "离职", "试用期", "劳动争议"],
        "security_level": 1,
    },
    {
        "filename": "07_绩效考核与晋升制度.md",
        "title": "绩效考核与晋升制度",
        "category_id": None,
        "category_name": "绩效晋升",
        "tags": ["绩效", "考核", "晋升", "奖惩", "OKR", "KPI"],
        "security_level": 1,
    },
    {
        "filename": "08_采购管理制度.md",
        "title": "采购管理制度",
        "category_id": None,
        "category_name": "采购管理",
        "tags": ["采购", "供应商", "招标", "合同", "验收"],
        "security_level": 2,
    },
    {
        "filename": "09_市场销售与客户服务管理制度.md",
        "title": "市场销售与客户服务管理制度",
        "category_id": None,
        "category_name": "销售管理",
        "tags": ["市场", "销售", "客户服务", "广告", "合同", "提成"],
        "security_level": 1,
    },
    {
        "filename": "10_法务合规管理制度.md",
        "title": "法务合规管理制度",
        "category_id": None,
        "category_name": "合同管理",
        "tags": ["法务", "合规", "合同", "知识产权", "反商业贿赂"],
        "security_level": 2,
    },
    {
        "filename": "11_薪资福利管理制度.md",
        "title": "薪资福利管理制度",
        "category_id": None,
        "category_name": "薪酬福利",
        "tags": ["薪酬", "工资", "社保", "公积金", "福利", "奖金", "加班"],
        "security_level": 1,
    },
]


def find_sample_docs_dir() -> Path:
    """查找 sample_docs 目录"""
    # 相对于脚本所在目录的上级目录
    candidates = [
        Path(__file__).parent.parent / "sample_docs",
        Path(__file__).parent.parent.parent / "sample_docs",
        Path.cwd().parent / "sample_docs",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        "找不到 sample_docs 目录。请确保 sample_docs 目录存在于项目根目录下。"
    )


def create_categories(db: Session) -> dict:
    """创建预定义分类，返回 {分类名称: 分类ID} 的映射"""
    category_map = {}
    created_by_name = {}

    # 按 sort_order 排序，确保父分类先创建
    sorted_cats = sorted(DEFAULT_CATEGORIES, key=lambda c: (c["parent_id"], c["sort_order"]))

    for cat_data in sorted_cats:
        parent_id = cat_data["parent_id"]
        # 如果 parent_id 是名字引用，转为实际 ID（通过 lookup）
        # 由于我们按顺序创建，父分类应该已经创建好了
        existing = db.query(Category).filter(
            Category.name == cat_data["name"],
            Category.parent_id == parent_id,
        ).first()

        if not existing:
            cat = Category(**cat_data)
            db.add(cat)
            db.flush()
            db.refresh(cat)
            category_map[cat.name] = cat.id
            # 记录以便后续子分类创建时查找 parent
        else:
            category_map[cat_data["name"]] = existing.id

    db.commit()
    return category_map


def create_seed_user(db: Session) -> int:
    """确保存在一个管理员用户用于种子数据"""
    from app.core.config import settings
    from app.core.security import hash_password
    from app.models.user import Role

    # 1. 先确保超级管理员角色存在
    super_admin_role = db.query(Role).filter(Role.code == "super_admin").first()
    if not super_admin_role:
        super_admin_role = Role(
            name="超级管理员",
            code="super_admin",
            description="系统全部权限",
            permissions=["*"],
        )
        db.add(super_admin_role)
        db.flush()
        db.refresh(super_admin_role)

    # 2. 再创建管理员用户（密码取自环境变量 ADMIN_PASSWORD，不硬编码）
    if not settings.ADMIN_PASSWORD:
        raise RuntimeError(
            "未配置 ADMIN_PASSWORD，拒绝创建管理员用户。"
            "请在 backend/.env 中设置 ADMIN_PASSWORD 为强密码后重试。"
        )
    admin = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
    if not admin:
        admin = User(
            username=settings.ADMIN_USERNAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            real_name="系统管理员",
            email=settings.ADMIN_EMAIL,
            department="信息技术部",
            role_id=super_admin_role.id,
            position="系统管理员",
            status=1,
        )
        db.add(admin)
        db.flush()
        db.refresh(admin)
        db.commit()
        print(f"  已创建管理员用户（{settings.ADMIN_USERNAME}，密码来自环境变量）")
    return admin.id


def seed_documents(db: Session, sample_docs_dir: Path, category_map: dict, admin_id: int):
    """导入种子文档"""
    from app.core.config import settings

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    created_count = 0
    skipped_count = 0

    for doc_info in SEED_DOCUMENTS:
        filename = doc_info["filename"]
        title = doc_info["title"]
        category_name = doc_info.get("category_name")
        category_id = category_map.get(category_name) if category_name else None

        # 检查是否已存在同名文档
        existing = db.query(Document).filter(Document.title == title).first()
        if existing:
            print(f"  [跳过] 文档已存在: {title}")
            skipped_count += 1
            continue

        # 查找源文件
        src_path = sample_docs_dir / filename
        if not src_path.exists():
            print(f"  [警告] 源文件不存在: {src_path}")
            continue

        # 复制到 uploads 目录（用中文原名，种子文档不担心重名）
        stored_name = filename
        dest_path = upload_dir / stored_name
        shutil.copy2(src_path, dest_path)

        # 读取文件大小
        file_size = dest_path.stat().st_size

        # 创建文档记录
        doc = Document(
            title=title,
            file_name=filename,
            file_path=str(dest_path),
            file_size=file_size,
            file_type="md",
            category_id=category_id,
            tags=doc_info.get("tags", []),
            security_level=doc_info.get("security_level", 1),
            status=0,  # 处理中
            created_by=admin_id,
            publish_date=date.today(),
        )
        db.add(doc)
        db.flush()
        db.refresh(doc)
        db.commit()  # 必须先提交，_process_document_task 用独立 session

        # 同步处理文档（确保在脚本退出前完成）
        print(f"  [处理] {title} (ID: {doc.id}) - 正在解析、分块、向量化...")
        _process_document_task(doc.id)
        created_count += 1

    print(f"\n共创建 {created_count} 个新文档，跳过 {skipped_count} 个已存在文档。")


def main():
    """主函数"""
    print("=" * 60)
    print("  企业制度知识库 - 种子数据导入工具")
    print("=" * 60)

    # 确保数据库表已创建
    print("\n[1/4] 初始化数据库...")
    Base.metadata.create_all(bind=engine)
    print("  数据库表已就绪。")

    # 查找 sample_docs
    print("\n[2/4] 查找种子文档...")
    try:
        sample_docs_dir = find_sample_docs_dir()
        print(f"  找到目录: {sample_docs_dir}")
        md_files = list(sample_docs_dir.glob("*.md"))
        print(f"  共 {len(md_files)} 个 Markdown 文件")
    except FileNotFoundError as e:
        print(f"  [错误] {e}")
        sys.exit(1)

    db = SessionLocal()
    try:
        # 创建分类
        print("\n[3/4] 创建文档分类...")
        category_map = create_categories(db)
        print(f"  共 {len(category_map)} 个分类")

        # 确保管理员用户
        admin_id = create_seed_user(db)
        print(f"  管理员用户 ID: {admin_id}")

        # 导入文档
        print("\n[4/4] 导入种子文档...")
        seed_documents(db, sample_docs_dir, category_map, admin_id)

    finally:
        db.close()

    print("\n" + "=" * 60)
    print("  导入完成！所有文档已处理完毕，可以开始问答了。")
    print("=" * 60)


if __name__ == "__main__":
    main()
