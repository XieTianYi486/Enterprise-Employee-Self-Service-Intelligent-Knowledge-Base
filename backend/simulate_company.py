# ============================================================
# 企业模拟测试数据生成器
# 模拟 80 人公司的员工账户、问答日志、会话记录
# 使用方法: cd backend && python simulate_company.py
# ============================================================

import sys, io, os, random, json, time, uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from app.db.sqlite import SessionLocal, engine, Base
from app.models.user import User, Role, Department
from app.models.chat import ChatSession, ChatMessage, ChatLog
from app.core.security import hash_password
from app.services.chat_service import get_chat_service

# ==================== 员工数据 ====================

DEPARTMENTS = [
    "技术研发部", "产品设计部", "市场推广部", "销售业务部",
    "人力资源部", "财务管理部", "行政管理部", "运营支持部",
    "法务合规部", "客户服务部",
]

# 各部门职位池：生成员工时按序取用，保证通讯录职位信息真实可感
POSITIONS = {
    "技术研发部": ["软件开发工程师", "测试工程师", "前端工程师", "后端工程师", "算法工程师", "系统架构师"],
    "产品设计部": ["产品经理", "UI设计师", "交互设计师", "产品助理"],
    "市场推广部": ["市场专员", "品牌专员", "新媒体运营", "推广经理"],
    "销售业务部": ["销售专员", "大客户经理", "商务专员", "销售主管"],
    "人力资源部": ["人事专员", "招聘专员", "培训专员", "薪酬专员"],
    "财务管理部": ["会计", "出纳", "财务专员", "审计专员"],
    "行政管理部": ["行政专员", "行政前台", "后勤专员"],
    "运营支持部": ["运营专员", "数据分析师", "运营主管"],
    "法务合规部": ["法务专员", "合规专员", "法务主管"],
    "客户服务部": ["客服专员", "客服主管", "售后专员"],
}

# 80个真实中文姓名
NAMES = [
    # 技术研发部 (12人)
    ("张伟", "技术研发部"), ("李娜", "技术研发部"), ("王强", "技术研发部"),
    ("刘洋", "技术研发部"), ("陈静", "技术研发部"), ("杨帆", "技术研发部"),
    ("赵敏", "技术研发部"), ("周杰", "技术研发部"), ("吴鑫", "技术研发部"),
    ("孙悦", "技术研发部"), ("马超", "技术研发部"), ("朱峰", "技术研发部"),
    # 产品设计部 (10人)
    ("黄丽", "产品设计部"), ("林涛", "产品设计部"), ("何芳", "产品设计部"),
    ("郑伟", "产品设计部"), ("梁晨", "产品设计部"), ("谢雨", "产品设计部"),
    ("宋宇", "产品设计部"), ("唐蕾", "产品设计部"), ("韩冰", "产品设计部"),
    ("曹阳", "产品设计部"),
    # 市场推广部 (8人)
    ("冯雪", "市场推广部"), ("董明", "市场推广部"), ("袁媛", "市场推广部"),
    ("邓凯", "市场推广部"), ("许洁", "市场推广部"), ("彭飞", "市场推广部"),
    ("蒋薇", "市场推广部"), ("沈浩", "市场推广部"),
    # 销售业务部 (10人)
    ("蔡林", "销售业务部"), ("潘安", "销售业务部"), ("田甜", "销售业务部"),
    ("杜强", "销售业务部"), ("任佳", "销售业务部"), ("姜辉", "销售业务部"),
    ("苏瑞", "销售业务部"), ("余光", "销售业务部"), ("叶欣", "销售业务部"),
    ("丁磊", "销售业务部"),
    # 人力资源部 (6人)
    ("程雪", "人力资源部"), ("陆瑶", "人力资源部"), ("段华", "人力资源部"),
    ("侯琳", "人力资源部"), ("龙飞", "人力资源部"), ("万芳", "人力资源部"),
    # 财务管理部 (6人)
    ("白洁", "财务管理部"), ("崔健", "财务管理部"), ("康敏", "财务管理部"),
    ("邱实", "财务管理部"), ("秦岚", "财务管理部"), ("江涛", "财务管理部"),
    # 行政管理部 (5人)
    ("史磊", "行政管理部"), ("顾欣", "行政管理部"), ("侯亮", "行政管理部"),
    ("邵杰", "行政管理部"), ("孟琴", "行政管理部"),
    # 运营支持部 (7人)
    ("汪波", "运营支持部"), ("毛宁", "运营支持部"), ("戴云", "运营支持部"),
    ("罗刚", "运营支持部"), ("夏雪", "运营支持部"), ("田峰", "运营支持部"),
    ("武艺", "运营支持部"),
    # 法务合规部 (3人)
    ("贺知", "法务合规部"), ("严冰", "法务合规部"), ("龙梅", "法务合规部"),
    # 客户服务部 (5人)
    ("钱多", "客户服务部"), ("汤圆", "客户服务部"), ("温馨", "客户服务部"),
    ("韦恩", "客户服务部"), ("甘露", "客户服务部"),
]

# 预设的 Q&A 对（覆盖所有分类，来自知识库内容）
QA_PAIRS = [
    # 考勤与休假
    ("年假可以休几天", "根据《员工考勤管理制度》，累计工作满1年不满10年的，每年享受带薪年休假5天；满10年不满20年的，每年10天；满20年的，每年15天。年假最小请假单位为半天，当年有效，可延期至次年3月31日。"),
    ("病假需要什么证明", "1天以内病假需提供正规医疗机构病历或诊断证明；2天及以上需提供二级甲等以上医院的病假证明；5天及以上还需提供检查/化验/住院等资料。病假1个月内按基本工资80%发放，1-3个月按60%发放。"),
    ("加班费怎么计算", "工作日加班按正常工资1.5倍计算，休息日加班按2倍计算（优先调休），法定节假日加班按3倍计算且不可调休。每日加班不超过3小时，每月累计不超过36小时。"),
    ("婚假有多少天", "符合法定结婚年龄的员工享受婚假3天；符合晚婚条件（男满25周岁、女满23周岁初婚）的增加7天，合计10天。婚假须在登记之日起一年内一次性休完，期间工资照发。"),
    ("产假怎么规定的", "女性员工生育享受产假98天（产前15天+产后83天）；难产增加15天；多胞胎每多一胎增加15天；符合计划生育政策的额外享受奖励假30天。男性员工享受陪产假15天。"),
    ("迟到怎么处理", "迟到10分钟以内口头提醒；10-30分钟按迟到时长扣减工资；30-60分钟按旷工半天处理；超过60分钟按旷工一天处理。单月累计超过5次的记书面警告。全勤奖200元/月。"),

    # 员工手册/入职
    ("入职需要准备哪些材料", "入职需提交：身份证原件及复印件、学历学位证书复印件、离职证明（应届生除外）、体检报告、银行卡复印件、一寸照片2张、社保转移单、资格证书复印件（如有）。"),
    ("试用期是多久", "劳动合同期限三年及以上的试用期不超过六个月；一年以上不满三年的不超过三个月。试用期员工享受同等薪酬福利，提前三日通知可解除合同。试用期结束前两周完成考核评估。"),
    ("公司有哪些福利", "公司提供：补充医疗保险、年度体检（800元/人）、节假日礼品、生日礼金200元、通讯补贴100-300元/月、工作日免费午餐、交通补贴200元/月、团建经费200元/季度、培训经费5000元/年、结婚/生育礼金各1000元。"),
    ("离职流程是怎样的", "主动辞职需提前30日（试用期3日）书面通知。流程：提交辞职申请→离职面谈→工作交接→财务结算→归还物品→办理社保转移→开具离职证明。竞业限制人员签有专门协议。"),

    # 差旅与报销
    ("出差住宿标准是多少", "住宿标准：一线城市（北上广深）普通员工400元/天、经理级500元/天、总监及以上800元/天；二线城市（省会）分别为300/400/600元；其他城市250/300/400元。超出部分自理。"),
    ("出差报销要什么票据", "交通费需提供行程单/火车票；住宿费需增值税发票；餐饮费需发票和消费明细。所有票据须真实完整，发票抬头为公司全称和纳税人识别号。出差返回后10个工作日内提交报销。"),
    ("出差审批流程", "普通员工出差由部门经理审批；部门经理由分管总监审批；总监及以上由副总裁审批；出国出境须总裁审批。出差前在OA提交申请单，注明事由、目的地、时间和预算。"),

    # 信息安全
    ("公司信息密级怎么分", "公司信息分为四个密级：绝密（红色标识，泄露造成特别严重损害，如核心算法/并购方案）、机密（橙色，造成严重损害，如客户名单/竞标方案）、内部（黄色，一般损害，如内部流程）、公开（绿色，可对外）。"),
    ("信息安全事件怎么报告", "发现安全事件后30分钟内向信息安全部门报告。禁止擅自处置或对外披露。一级事件（核心系统被入侵）30分钟内启动应急，二级2小时，三级4小时，四级24小时。涉及个人信息泄露的72小时内报告监管部门。"),
    ("密码设置有什么要求", "密码长度不少于12位，须包含大小写字母、数字和特殊字符。重要系统（财务/HR/客户数据）须开启双因素认证。密码不得共享，不得用浏览器记住密码，每90天修改一次，不得与前5次重复。"),

    # IT设备
    ("IT设备故障怎么报修", "通过IT服务台（企业微信/Web/电话）提交工单，注明设备型号、故障现象和影响范围。紧急故障（影响多人工作）30分钟内响应，高优先级1小时，中优先级4小时，低优先级1个工作日。保修期内免费维修，维修期间提供备机。"),
    ("公司电脑多久换一次", "笔记本电脑3年更换（开发/设计岗可缩短至2年）；台式电脑/工作站4年；显示器5年；服务器5年（核心业务可提前至4年）；移动设备2年。提前更换需满足故障维修成本超残值50%的条件。"),
    ("可以自己装软件吗", "IT部门维护软件白名单，名单内可自行安装。名单外须提交申请，经安全评估和合规审核后安装。禁止安装盗版软件、P2P工具、未经批准的VPN、挖矿软件和来源不明的软件。开源软件需审核许可证合规性。"),

    # 绩效考核
    ("绩效考核怎么评级", "考核等级和比例分布：S(卓越)≤5%、A(优秀)≤15%、B+(良好)≤35%、B(胜任)不限制、C(待改进)≥5%、D(不合格)≥2%。季度考核含自评、上级评估、隔级校准、结果反馈四个环节。连续两次C或一次D进入PIP改进计划。"),
    ("晋升需要什么条件", "晋升基本条件：在当前职级满1年以上，最近两次考核均为B+及以上。破格晋升需最近一次为S(卓越)。P1→P2需满1年+技能认证；P3→P4需满2年+主导跨部门项目；M1→M2需满1.5年+团队≥3人。每年1月和7月组织评审。"),
    ("绩效申诉怎么申请", "在绩效反馈面谈后5个工作日内通过HR系统提交申诉表。受理条件：考核程序违规、评价基于明显失实信息、存在个人偏见或打击报复。HR在3个工作日内确认受理，15个工作日内完成调查和复议，复议结果为最终结果。"),

    # 财务
    ("采购审批的分级标准", "采购金额<5000元由部门经理审批；5000-50000元需分管总监+采购经理；50000-200000元需采购总监+财务总监；200000-1000000元需总经理；超过1000000元需董事会。"),
    ("报销标准是什么", "业务招待费人均≤200元/餐（重要客户≤400元）；会议费≤300元/人/天；培训费年预算5000元/人；市内公出优先公交，加班至21:00后可报销打车；私家车因公使用按1.2元/公里报销。发票须公司全称和税号，30日内报销。"),
    ("合同付款需要什么凭证", "付款申请需附：采购合同、验收报告、发票、采购申请单。质保金一般为合同金额5%-10%。预付款不超过30%且须有担保。所有付款通过银行转账至供应商对公账户。发票须为增值税专用发票。"),

    # 劳动合同
    ("辞职需要提前多久通知", "试用期员工提前3日通知，正式员工提前30日书面通知。流程：提交辞职申请书→直属上级面谈→HR离职面谈→工作交接→财务结算→离职。未按规定通知造成损失的应承担相应责任。"),
]

# 预定义会话标题
SESSION_TITLES = [
    "新人入职制度咨询", "年假福利确认", "出差报销疑问",
    "绩效考核了解", "IT设备使用问题", "信息安全培训",
    "离职流程咨询", "请假申请了解", "工资发放疑问",
    "社保政策咨询", "加班规定确认", "办公设备申请",
    "培训报名咨询", "晋升条件了解", "合同续签问题",
]


def create_departments(db):
    """创建10个部门"""
    dept_descriptions = {
        "技术研发部": "负责公司核心产品的技术研发、架构设计、代码开发和测试",
        "产品设计部": "负责产品规划、需求分析、UI/UX设计和产品迭代管理",
        "市场推广部": "负责品牌推广、市场营销、广告投放和活动策划",
        "销售业务部": "负责客户开发、销售业绩、合同签订和客户关系维护",
        "人力资源部": "负责招聘、培训、薪酬绩效、员工关系和HR政策制定",
        "财务管理部": "负责财务核算、预算管理、资金管控和税务申报",
        "行政管理部": "负责办公环境、资产管理、行政后勤和会议管理",
        "运营支持部": "负责业务运营、数据分析、客服支持和流程优化",
        "法务合规部": "负责合同审查、法律咨询、合规审计和知识产权管理",
        "客户服务部": "负责客户咨询、投诉处理、售后服务和满意度跟踪",
    }
    existing_names = {d.name for d in db.query(Department).all()}
    created = 0
    for i, (name, desc) in enumerate(dept_descriptions.items()):
        if name not in existing_names:
            db.add(Department(
                name=name, description=desc,
                sort_order=i + 1, parent_id=0,
            ))
            created += 1
    db.commit()
    print(f"  ✓ 创建 {created} 个新部门 (共{len(dept_descriptions)}个)")
    return {d.name: d for d in db.query(Department).all()}


def create_roles(db):
    """确保角色存在"""
    existing = {r.code: r for r in db.query(Role).all()}
    default_roles = [
        ("employee", "普通员工", ["chat:ask", "documents:read",
                                  "leaves:read", "leaves:submit",
                                  "expenses:read", "expenses:submit"]),
        ("dept_admin", "部门管理员", ["documents:read", "stats:read", "chat:ask",
                                     "leaves:read", "expenses:read",
                                     "approvals:read", "approvals:approve"]),
        ("knowledge_admin", "知识库管理员", ["documents:*", "categories:*",
                                            "logs:read", "stats:read", "chat:ask"]),
        ("boss", "总经理", ["chat:ask", "documents:read", "stats:read",
                           "leaves:read", "expenses:read",
                           "approvals:read", "approvals:approve"]),
        ("super_admin", "超级管理员", ["*"]),
    ]
    role_map = {}
    for code, name, perms in default_roles:
        if code not in existing:
            r = Role(name=name, code=code, description=f"{name}角色", permissions=perms)
        else:
            r = existing[code]
        db.add(r)
        db.flush()
        role_map[code] = r
    db.commit()
    return role_map


def create_users(db, role_map, dept_map):
    """创建80个员工账户"""
    existing = {u.username for u in db.query(User).all()}
    created = 0

    for i, (name, dept) in enumerate(NAMES):
        # 生成用户名：姓氏拼音 + 数字
        import pypinyin
        py = pypinyin.lazy_pinyin(name[0]) if name else f"user{i}"
        username = f"{''.join(py)}{random.randint(10, 99)}"
        if username in existing:
            username = f"{''.join(py)}{random.randint(100, 999)}"

        # 分配角色：大部分普通员工，少部分部门管理员
        if i % 15 == 0:
            role = role_map["dept_admin"]
            position = "部门经理"
        elif i % 30 == 0:
            role = role_map["knowledge_admin"]
            position = "知识库管理员"
        else:
            role = role_map["employee"]
            pool = POSITIONS.get(dept, ["职员"])
            position = pool[i % len(pool)]

        user = User(
            username=username,
            password_hash=hash_password("test123"),
            real_name=name,
            email=f"{username}@company.cn",
            phone=f"138{random.randint(10000000, 99999999)}",
            dept_id=dept_map.get(dept).id if dept_map.get(dept) else None,
            role_id=role.id,
            position=position,
            status=1,
        )
        db.add(user)
        db.flush()
        created += 1

    db.commit()
    print(f"  ✓ 创建 {created} 个员工账户 (密码统一: test123)")
    return db.query(User).filter(User.status == 1).all()


def create_sessions_and_logs(db, users):
    """为随机用户创建会话和问答日志"""
    chat_service = get_chat_service()
    normal_users = [u for u in users if u.role_id in [1, 2, 3]]  # 非超级管理员
    random.shuffle(normal_users)

    total_sessions = 0
    total_messages = 0
    total_logs = 0
    real_qa_count = 0

    now = datetime.now(timezone.utc)

    # === 第一轮：用真实 RAG 系统生成 20 条问答 ===
    print("\n  🔍 使用真实 RAG 系统生成问答 (前20条)...")
    real_questions = random.sample(QA_PAIRS, min(20, len(QA_PAIRS)))

    for idx, (question, _) in enumerate(real_questions):
        user = normal_users[idx % len(normal_users)]
        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        created_at = now - timedelta(
            days=random.randint(0, 14),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )

        # 创建会话
        session = ChatSession(
            id=session_id, user_id=user.id,
            title=random.choice(SESSION_TITLES),
            message_count=2, last_message_at=created_at,
            created_at=created_at,
        )
        db.add(session)

        # 创建用户消息
        user_msg = ChatMessage(
            session_id=session_id, role="user",
            content=question, created_at=created_at,
        )
        db.add(user_msg)

        # 调用真实RAG获取回答
        try:
            result = chat_service.ask(question=question, security_level=4)
            answer = result["answer"]
            sources = result.get("sources", [])
            latency = result.get("latency", {})
            usage = result.get("usage", {})
            real_qa_count += 1
        except Exception:
            # RAG失败时用预设答案
            answer = QA_PAIRS[idx][1]
            sources = []
            latency = {"retrieval_ms": 0, "llm_ms": 0, "total_ms": 0}
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # 创建助手消息
        assistant_msg = ChatMessage(
            session_id=session_id, role="assistant",
            content=answer,
            sources=json.dumps(sources, ensure_ascii=False) if sources else None,
            token_count=usage.get("total_tokens", 0),
            created_at=created_at + timedelta(seconds=random.randint(2, 10)),
        )
        db.add(assistant_msg)

        # 创建日志
        log = ChatLog(
            session_id=session_id, user_id=user.id,
            question=question, answer=answer,
            source_doc_ids=[s.get("document_id") for s in sources],
            is_answered=1 if sources else 0,
            feedback=random.choice([0, 0, 0, 0, 1, 1, 2]),  # 多数无反馈，少数点赞/踩
            feedback_reason=random.choice([None, None, None, "回答准确", "不够详细", "信息不全"]),
            retrieval_ms=latency.get("retrieval_ms", 0),
            llm_ms=latency.get("llm_ms", 0),
            total_ms=latency.get("total_ms", 0),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            created_at=assistant_msg.created_at,
        )
        db.add(log)

        total_sessions += 1
        total_messages += 2
        total_logs += 1

        if (idx + 1) % 10 == 0:
            db.commit()
            print(f"    ... {idx + 1}/{len(real_questions)} 完成")

    db.commit()
    print(f"    ✓ 真实RAG问答: {real_qa_count}/{len(real_questions)} 条")

    # === 第二轮：用预设 Q&A 批量生成更多日志 ===
    print(f"\n  📝 批量生成预设问答日志...")
    bulk_users = normal_users * 5  # 每个用户可多次提问
    random.shuffle(bulk_users)

    for idx in range(150):
        question, answer = random.choice(QA_PAIRS)
        user = bulk_users[idx % len(bulk_users)]
        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        created_at = now - timedelta(
            days=random.randint(0, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )

        # 随机决定这条是否命中
        is_answered = random.choices([1, 0], weights=[85, 15])[0]
        if not is_answered:
            answer = "抱歉，知识库中未找到相关信息，建议您咨询HR部门。"

        source_ids = [random.randint(1, 9)] if is_answered else []

        # 会话
        db.add(ChatSession(
            id=session_id, user_id=user.id,
            title=random.choice(SESSION_TITLES),
            message_count=2,
            last_message_at=created_at + timedelta(seconds=random.randint(1, 15)),
            created_at=created_at,
        ))

        # 用户消息
        db.add(ChatMessage(
            session_id=session_id, role="user",
            content=question, created_at=created_at,
        ))

        # 助手消息
        db.add(ChatMessage(
            session_id=session_id, role="assistant",
            content=answer,
            sources=json.dumps([{"document_id": did, "document_name": f"doc_{did}"} for did in source_ids], ensure_ascii=False) if source_ids else None,
            created_at=created_at + timedelta(seconds=random.randint(2, 12)),
        ))

        # 日志
        feedback = random.choices([0, 1, 2], weights=[55, 35, 10])[0]
        reasons_map = {1: [None, "回答准确", "很详细", "帮了大忙"], 2: [None, "回答不准确", "不够详细", "信息过时"]}
        db.add(ChatLog(
            session_id=session_id, user_id=user.id,
            question=question, answer=answer,
            source_doc_ids=source_ids,
            is_answered=is_answered,
            feedback=feedback,
            feedback_reason=random.choice(reasons_map.get(feedback, [None])),
            retrieval_ms=random.randint(50, 300),
            llm_ms=random.randint(500, 3000),
            total_ms=random.randint(600, 3500),
            prompt_tokens=random.randint(200, 2000),
            completion_tokens=random.randint(100, 800),
            created_at=created_at + timedelta(seconds=random.randint(2, 15)),
        ))

        total_sessions += 1
        total_messages += 2
        total_logs += 1

        if (idx + 1) % 50 == 0:
            db.commit()
            print(f"    ... {idx + 1}/150 完成")

    db.commit()
    print(f"    ✓ 预设问答: 150 条")
    print(f"\n  📊 总计: {total_sessions} 会话, {total_messages} 消息, {total_logs} 日志")


def main():
    print("=" * 56)
    print("  模拟企业数据生成器 (80人公司)")
    print("=" * 56)

    db = SessionLocal()
    try:
        # 1. 创建部门
        print("\n[1/5] 创建部门...")
        dept_map = create_departments(db)

        # 2. 确保角色
        print("\n[2/5] 初始化角色...")
        role_map = create_roles(db)
        print(f"  ✓ {len(role_map)} 个角色就绪")

        # 3. 创建用户
        print(f"\n[3/5] 创建员工账户 (目标 {len(NAMES)} 人)...")
        users = create_users(db, role_map, dept_map)

        # 4. 生成问答日志
        print("\n[4/5] 生成问答日志与会话...")
        create_sessions_and_logs(db, users)

        # 5. 最终统计
        print("\n[5/5] 最终统计...")
        user_count = db.query(User).filter(User.status == 1).count()
        session_count = db.query(ChatSession).count()
        message_count = db.query(ChatMessage).count()
        log_count = db.query(ChatLog).count()
        answered = db.query(ChatLog).filter(ChatLog.is_answered == 1).count()
        liked = db.query(ChatLog).filter(ChatLog.feedback == 1).count()

        dept_stats = {}
        for u in db.query(User).filter(User.status == 1).all():
            dname = u.dept.name if u.dept else "未分配"
            dept_stats[dname] = dept_stats.get(dname, 0) + 1

        print(f"  👥 员工: {user_count} 人")
        print(f"  🏢 部门: {len(dept_stats)} 个")
        for dept, cnt in sorted(dept_stats.items(), key=lambda x: -x[1]):
            print(f"     {dept}: {cnt}人")
        print(f"  💬 会话: {session_count}")
        print(f"  📝 消息: {message_count}")
        print(f"  📋 日志: {log_count}")
        print(f"  ✅ 命中率: {round(answered/log_count*100,1)}%" if log_count > 0 else "  -")
        print(f"  👍 满意度: {round(liked/answered*100,1)}%" if answered > 0 else "  -")

    finally:
        db.close()

    print(f"\n{'='*56}")
    print("  模拟完成！登录前端即可查看问答日志和统计数据")
    print(f"  普通员工测试账号: 任意用户名, 密码: test123")
    print(f"  管理员账号: admin（密码为 .env 中的 ADMIN_PASSWORD，不在此处输出）")
    print(f"{'='*56}")


if __name__ == "__main__":
    main()
