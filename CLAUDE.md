# 企业员工自助服务系统 — 产品文档

## 项目基本信息

- **项目名称**：企业员工自助服务系统（Enterprise Employee Self-Service System, EESS）
- **项目类型**：企业员工自助服务平台（OA 办公流程 + RAG 制度知识服务）
- **目标用户**：企业内部员工、HR、行政、知识库管理员、超级管理员
- **部署方式**：私有化部署，支持完全内网运行
- **数据存储**：SQLite（开发）/ MySQL（生产）+ ChromaDB 向量库

---

## 产品功能需求

### 1. 文档管理
- 多格式文档上传（PDF、Word、Excel、Markdown、纯文本）
- 自动解析、分块、向量化、分类标签、版本管理
- 支持文档密级（公开、内部、机密、绝密）与权限过滤

### 2. 智能问答
- 基于 RAG 的多路召回（向量检索 + BM25 关键词检索）+ 重排序
- 多轮对话上下文理解、查询改写
- 答案溯源（显示文档名称、章节、页码）
- 幻觉抑制与拒答机制
- 流式输出（SSE）

### 3. 办公流程（OA 核心）
- 请假管理：年假/事假/病假/调休/婚假，假期余额按年管理、审批通过自动扣减
- 报销管理：差旅/办公用品/招待/交通等类型，发票凭证上传（私有存储+鉴权下载）
- 两级审批引擎：员工→部门经理→（请假>3天/报销>5000元）→总经理终审；经理本人申请直达总经理；驳回关闭；审批流水全程留痕
- 考勤打卡（简化版）：上下班打卡、迟到/早退四态评定、部门月度汇总

### 4. 用户权限
- RBAC 五角色模型（普通员工、部门管理员、总经理、知识库管理员、超级管理员）+ 细粒度权限点
- JWT Token 认证 + 登录失败锁定 + 算式验证码
- 文档密级（公开/内部/机密/绝密）与用户角色匹配的检索过滤

### 5. 信息与协同
- 公告管理（Markdown、有效期）、站内消息中心（审批/工单结果自动通知+未读角标）
- 工单闭环：知识库答不了→一键转工单→管理员回复
- 通讯录（部门组织树+成员信息）、分角色工作台（ECharts 统计看板）

### 6. 系统管理
- 问答日志审计（记录每次问答的耗时、来源、反馈）
- 统计分析（问答量趋势、高频问题、未命中问题、用户满意度）
- 敏感词拦截、操作审计日志、系统配置热更新

---

## 技术架构

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     展示层 (Presentation)                │
│  Vue 3 前端 (管理后台 + 对话界面)                         │
├─────────────────────────────────────────────────────────┤
│                     应用层 (Application)                 │
│  FastAPI 后端 ─ 用户认证 │ 办公流程(请假/报销/审批) │ 考勤 │
│  文档管理 │ 问答服务 │ 工单 │ 消息中心 │ 工作台 │ 日志审计 │
├─────────────────────────────────────────────────────────┤
│                     检索层 (Retrieval)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐          │
│  │ 向量检索  │  │ BM25检索 │  │ 混合检索+融合 │          │
│  └──────────┘  └──────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────┤
│                     数据层 (Data)                        │
│  ChromaDB 向量库 │ SQLite/MySQL │ BM25 索引 │ 文件存储  │
└─────────────────────────────────────────────────────────┘
```

### 技术栈

#### 后端 (backend/)
| 类别 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | AI/ML 生态最完善 |
| Web 框架 | FastAPI | 高性能异步，自动生成 API 文档 |
| 数据库 ORM | SQLAlchemy 2.0 | 同步模式，支持 SQLite / MySQL |
| 向量数据库 | ChromaDB | 嵌入式向量存储，自带持久化 |
| 关键词检索 | rank-bm25 | 轻量 BM25 算法实现 |
| LLM 接入 | 阿里云百炼 DashScope | 通义千问系列模型 |
| 文档解析 | PyMuPDF / python-docx / openpyxl | 多格式文档解析 |
| 认证 | JWT + Passlib + bcrypt | Token 认证与密码加密 |
| 缓存 | cachetools + diskcache | 问答缓存与会话缓存 |
| 日志 | Loguru | 结构化日志 |
| 测试 | PyTest + pytest-asyncio | 后端测试框架 |

#### 前端 (frontend/)
| 类别 | 技术 | 说明 |
|------|------|------|
| 框架 | Vue 3 + TypeScript | 渐进式框架 |
| UI 组件库 | Element Plus | 企业级 UI 组件库 |
| 状态管理 | Pinia | Vue 官方推荐 |
| 路由 | Vue Router 4 | 官方路由 |
| HTTP 客户端 | Axios | 请求拦截与 Token 管理 |
| Markdown 渲染 | markdown-it | 渲染 LLM 返回的 Markdown |
| 代码高亮 | highlight.js | 代码块语法高亮 |
| 构建工具 | Vite | 快速构建 |

---

## 项目目录结构

```
Enterprise Employee Self-Service Intelligent Knowledge Base/
├── backend/
│   ├── app/
│   │   ├── api/              # API 路由层
│   │   │   ├── v1/           # v1 版本接口
│   │   │   │   ├── auth.py         # 认证接口（注册/登录/验证码）
│   │   │   │   ├── chat.py         # 问答接口（同步/SSE 流式）
│   │   │   │   ├── documents.py    # 文档管理接口
│   │   │   │   ├── workflow.py     # OA 流程接口（请假/报销/两级审批）
│   │   │   │   ├── attendance.py   # 考勤打卡接口
│   │   │   │   ├── contacts.py     # 通讯录组织树
│   │   │   │   ├── notifications.py# 站内消息中心
│   │   │   │   ├── workbench.py    # 分角色工作台统计
│   │   │   │   ├── tickets.py      # 工单闭环（员工+管理员）
│   │   │   │   ├── security.py     # 敏感词/审计日志
│   │   │   │   └── admin.py        # 管理接口（用户/角色/统计）
│   │   │   └── deps.py          # 依赖注入（获取当前用户等）
│   │   ├── core/             # 核心模块
│   │   │   ├── config.py        # 配置管理（Pydantic Settings）
│   │   │   ├── security.py      # JWT + 密码哈希
│   │   │   └── exceptions.py    # 自定义异常
│   │   ├── models/           # SQLAlchemy 数据模型（用户/文档/聊天/OA）
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   ├── services/         # 业务逻辑层
│   │   │   ├── auth_service.py       # 注册/登录/密码修改
│   │   │   ├── captcha_service.py    # 算式验证码
│   │   │   ├── chat_service.py       # RAG 问答编排
│   │   │   ├── document_service.py   # 文档管理
│   │   │   ├── workflow_service.py   # 请假/报销/两级审批引擎
│   │   │   ├── attendance_service.py # 考勤打卡
│   │   │   ├── notification_service.py # 站内消息
│   │   │   ├── audit_service.py      # 审计日志
│   │   │   └── sensitive_service.py  # 敏感词拦截
│   │   ├── tasks/            # 异步任务（文档处理）
│   │   ├── db/               # 数据库连接
│   │   │   ├── sqlite.py        # SQLAlchemy 引擎 + Session
│   │   │   ├── chroma_client.py # ChromaDB 客户端
│   │   │   └── cache.py         # 缓存管理
│   │   ├── rag/              # RAG 核心引擎
│   │   │   ├── chunker/         # 文档分块
│   │   │   ├── embeddings/      # 向量嵌入（DashScope）
│   │   │   ├── retrievers/      # 检索引擎（向量/BM25/混合）
│   │   │   ├── query_processor/ # 查询预处理（改写/意图识别）
│   │   │   ├── llm/             # LLM 调用封装
│   │   │   ├── prompts/         # Prompt 模板
│   │   │   ├── reranker/        # 重排序
│   │   │   └── ingestion.py     # 文档入库流程
│   │   ├── static/           # 头像等静态资源
│   │   └── main.py           # 应用入口
│   ├── data/                 # SQLite 数据文件
│   ├── cache/                # 磁盘缓存
│   ├── uploads/              # 上传的文档文件
│   ├── tests/                # PyTest 测试
│   ├── requirements.txt
│   ├── seed_documents.py     # 示例制度文档入库脚本
│   ├── simulate_company.py   # 80 人模拟公司数据生成脚本
│   └── rebuild_indexes.py    # 检索索引重建脚本
├── frontend/
│   ├── src/
│   │   ├── api/              # API 调用封装
│   │   │   ├── client.ts        # Axios 实例与拦截器
│   │   │   ├── auth.ts / chat.ts / session.ts
│   │   │   ├── workflow.ts      # OA 流程接口（请假/报销/审批）
│   │   │   ├── ticket.ts        # 工单接口
│   │   │   └── security.ts      # 验证码/安全接口
│   │   ├── views/            # 页面组件
│   │   │   ├── auth/            # 登录/注册/个人中心
│   │   │   ├── chat/            # 对话问答界面
│   │   │   ├── documents/       # 员工文档浏览
│   │   │   ├── oa/              # 请假/报销/审批/考勤
│   │   │   ├── tickets/         # 我的工单
│   │   │   ├── admin/           # 管理后台（12 个管理页）
│   │   │   ├── ContactsPage.vue # 通讯录
│   │   │   ├── WorkbenchPage.vue# 分角色工作台
│   │   │   └── NotificationsPage.vue # 消息中心
│   │   ├── components/       # 公共组件（布局/图表等）
│   │   ├── store/            # Pinia 状态管理（auth/chat/theme）
│   │   ├── router/           # Vue Router 路由配置（含权限守卫）
│   │   ├── styles/           # 全局样式
│   │   ├── utils/            # 工具函数（导出/打印）
│   │   ├── App.vue
│   │   └── main.ts
│   ├── package.json
│   └── vite.config.ts
├── sample_docs/              # 示例制度文档
├── picture/                  # README 系统预览截图
├── .claude/                  # Claude Code 配置
│   ├── agents/               # 子代理定义
│   ├── commands/             # 自定义斜杠命令
│   ├── check-results/        # 质量检查结果
│   └── settings.json         # 权限配置
├── start_all.bat             # 一键启动前后端
├── start_backend.bat
└── start_frontend.bat
```

---

## 🚀 如何运行

### 环境准备
- Python 3.10+
- Node.js 18+
- 阿里云百炼 API Key（DashScope）

### 后端
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env    # 编辑 .env 填入 API Key
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 前端
```bash
cd frontend
npm install
npm run dev             # 访问 http://localhost:5173
```

### 一键启动
```bash
start_all.bat
```

### 运行测试
```bash
cd backend
python -m pytest -v
```

---

## 开发协作规则

1. **代码质量**：提交前确保通过测试和质量检查（使用 `/git-save` 或让 gitcommit-agent 处理）
2. **API 规范**：统一响应格式 `{code, message, data}`；错误码 1xxx 参数错误、2xxx 认证错误、3xxx 业务错误、4xxx 系统错误
3. **Python 规范**：使用 type hints、docstring 注释、Pydantic 做数据校验
4. **Vue 规范**：使用 `<script setup lang="ts">` 语法、Pinia store 管理状态
5. **安全原则**：JWT 认证、密码 bcrypt 哈希、文档密级过滤、API 参数校验

---

## 关键配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 后端端口 | 8001 | FastAPI 服务端口 |
| 前端端口 | 5173 | Vite 开发服务器 |
| 向量维度 | 1536 | DashScope text-embedding-v2 |
| 分块大小 | 512 token | 语义分块 |
| 召回 Top-K | 20 | 向量/BM25 双路召回数量，重排后取 5 |
| JWT 过期 | 24h | Token 有效期 |
| 请假升级阈值 | 3 天 | 超过需总经理终审（LEAVE_BOSS_APPROVAL_DAYS） |
| 报销升级阈值 | 5000 元 | 超过需总经理终审（EXPENSE_BOSS_APPROVAL_AMOUNT） |
| 考勤时间 | 09:00-18:00 | 上下班打卡规则（WORK_START/END_HOUR） |

---

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/auth/login | 用户登录 |
| POST | /api/v1/auth/register | 用户注册 |
| GET | /api/v1/auth/me | 当前用户信息 |
| POST | /api/v1/chat/ask | 问答（同步） |
| POST | /api/v1/chat/stream | 问答（SSE 流式，无 LLM 时降级检索直出） |
| GET | /api/v1/chat/sessions | 会话列表 |
| POST | /api/v1/documents/upload | 上传文档 |
| GET | /api/v1/documents | 文档列表 |
| POST | /api/v1/leaves | 提交请假申请 |
| GET | /api/v1/leaves/balance | 我的假期余额 |
| POST | /api/v1/expenses | 提交报销申请 |
| GET | /api/v1/approvals/todo | 审批待办 |
| GET | /api/v1/approvals/done | 审批已办 |
| POST | /api/v1/approvals/{biz}/{id} | 审批动作（两级审批引擎） |
| POST | /api/v1/attendance/clock | 考勤打卡/签退 |
| GET | /api/v1/attendance/my | 我的月度考勤 |
| GET | /api/v1/notifications | 我的站内消息（含未读数） |
| POST | /api/v1/tickets | 提交工单（问答转工单） |
| GET | /api/v1/workbench/stats | 分角色工作台统计 |
| GET | /api/v1/contacts/tree | 通讯录组织树 |
| GET | /api/v1/admin/stats/overview | 统计概览 |
| GET | /api/v1/admin/audit-logs | 操作审计日志 |
| GET | /api/health | 健康检查 |
