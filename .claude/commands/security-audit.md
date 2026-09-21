---
description: 安全审计——检测 API Key 泄露、注入漏洞、JWT 配置、Python 反序列化等安全隐患
---

你是一位**安全审计专家**。请对本项目进行全面的安全审查，按以下清单逐一排查，并给出审计报告。

本项目的技术栈：
- **后端**：Python / FastAPI / SQLAlchemy / ChromaDB / DashScope（阿里云百炼）
- **前端**：Vue 3 / TypeScript / Element Plus / Axios
- **认证**：JWT + bcrypt

---

## 🔍 审查清单（5 大类 + 扩展项）

### 一、敏感信息硬编码

> 检查代码中是否直接写了密码、API 密钥、Token 等敏感信息。

**排查模式：**

| 可疑特征 | 示例 |
|---------|------|
| 硬编码密码 | `password = "admin123"` / `passwd: '123456'` |
| API 密钥 | `api_key = "sk-xxx"` / `DASHSCOPE_API_KEY = "xxx"` |
| JWT / Token 密钥 | `SECRET_KEY = "mysecret"` / `"secret": "dev-secret"` |
| 数据库连接串 | `mysql://admin:123456@localhost` |
| 私钥 | `-----BEGIN RSA PRIVATE KEY-----` |
| 内网地址 | `10.0.0.1` / `192.168.1.1` |
| 个人信息 | 手机号(1[3-9]\d{9}) / 身份证号 / 邮箱 |

**重点检查文件：**
- `backend/.env` — 是否被 Git 跟踪
- `backend/app/core/config.py` — 是否有硬编码的默认值
- `backend/app/core/security.py` — JWT Secret 是否硬编码
- `frontend/.env*` — 是否有前端环境变量暴露敏感信息
- `frontend/src/` 下所有 `.ts` `.vue` 文件

**排查方法：**
用 `grep` 搜索关键词：`password`, `passwd`, `secret`, `token`, `apikey`, `api_key`, `private.key`, `BEGIN RSA`, `jwt`, `auth`, `credential`, `dashscope`, `DASHSCOPE_API_KEY`

### 二、注入漏洞风险

**Python 后端特有：**

| 漏洞类型 | 危险信号 | 安全做法 |
|---------|---------|---------|
| SQL 注入 | 字符串拼接构造 SQL（`f"SELECT * FROM users WHERE name = '{input}'"`） | SQLAlchemy 参数化查询 |
| 命令注入 | `os.system(f"ls {userInput}")` / `subprocess.call(userInput, shell=True)` | 使用参数数组、禁用 shell |
| 代码注入 | `eval(userInput)` / `exec(userInput)` / `pickle.loads(userInput)` | **绝对禁止** eval/exec；用 json 替代 pickle |
| 路径遍历 | `open(userPath)` 未校验（`../../etc/passwd`） | 限制目录范围、拒绝 `..` |
| Prompt 注入 | 用户输入直接拼接到 LLM Prompt 中，可能绕过系统指令 | 对用户输入做过滤；系统指令与用户输入明确分隔 |

**前端 Vue 特有：**

| 漏洞类型 | 危险信号 | 安全做法 |
|---------|---------|---------|
| XSS | 直接使用 `v-html` 渲染用户输入 | 默认使用文本插值、对 HTML 做 sanitize |
| CSRF | 状态变更接口无防护 | JWT Bearer Token 已提供一定防护 |

**排查方法：**
- Python: 搜索 `eval(` / `exec(` / `pickle` / `os.system` / `subprocess` / `shell=True`
- Python + SQLAlchemy: 搜索 `.execute(f"` / `.execute("SELECT` / `text(f"`（原生 SQL 拼接）
- Vue: 搜索 `v-html`
- ChromaDB: 检查查询条件是否直接使用用户输入

### 三、配置文件与部署安全

| 检查项 | 说明 |
|--------|------|
| .env 未 gitignore | `backend/.env` 是否被 Git 跟踪 |
| 默认密码 | `.env` 中的 `ADMIN_PASSWORD` 是否仍是弱密码 |
| .gitignore 完整性 | 是否包含 `.env`、`*.db`、`__pycache__/`、`node_modules/`、`dist/`、`chroma_data/` |
| DEBUG 模式 | FastAPI `debug=True` 是否会在生产环境开启 |
| CORS 配置 | `allow_origins` 是否为 `["*"]`（生产环境应限制域名） |
| 日志泄露 | 是否在日志中打印了密码、Token、用户输入等敏感信息 |
| 错误信息泄露 | API 返回的异常信息是否包含数据库结构、堆栈信息 |
| JWT 过期 | `ACCESS_TOKEN_EXPIRE_MINUTES` 是否过长 |

### 四、认证与权限

| 检查项 | 说明 |
|--------|------|
| 🔓 缺少鉴权 | 是否有 API 接口忘记添加 `get_current_user` 依赖 |
| 🔑 JWT 算法 | 是否使用了安全的签名算法（HS256/RS256），不应使用 `none` |
| 🔐 权限粒度 | 接口是否有正确的角色/权限校验（普通员工不应能访问管理接口） |
| 📁 文档权限 | 文档密级过滤是否在所有检索路径上生效（向量检索 + BM25 + 混合检索） |
| 🍪 Token 存储 | 前端 JWT Token 存储在 localStorage（可能被 XSS 读取）还是 httpOnly Cookie |

### 五、依赖与供应链

| 检查项 | 说明 |
|--------|------|
| 📦 Python 依赖 | `requirements.txt` 中是否有已知漏洞的旧版本（检查 DashScope SDK 版本） |
| 📦 npm 依赖 | `npm audit` 是否有高危漏洞（特别注意 markdown-it 的 XSS 历史漏洞） |
| 🔗 第三方模型 | DashScope 调用是否走 HTTPS、API Key 是否通过环境变量注入 |
| 📄 ChromaDB | ChromaDB 版本是否有已知安全问题 |

---

## 执行流程

### 第一步：收集信息
1. 检查 `.gitignore` 内容，确认敏感文件已被排除
2. 用 `git ls-files` 检查 `.env` 是否被 Git 跟踪
3. 运行 `pip list --outdated` 检查 Python 依赖更新
4. 运行 `npm audit`（在 `frontend/` 目录）检查 JS 依赖漏洞

### 第二步：逐项审查
按上述五大类逐项排查，使用 grep 搜索可疑模式，发现隐患后记录到报告中。

### 第三步：输出审计报告

---

## 输出格式

```
🔐 安全审计报告 — 企业员工自助服务系统 — [日期]
==========================================================

风险评级：🔴 高危 / 🟡 中危 / 🟢 低危
共发现 X 个安全问题

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 严重（必须立即修复）       N 个
───────────────────────────────
| # | 文件:行号 | 类型 | 问题 | 修复建议 |
|---|----------|------|------|---------|

🟡 警告（建议尽快修复）       N 个
───────────────────────────────
| # | 文件:行号 | 类型 | 问题 | 修复建议 |
|---|----------|------|------|---------|

🟢 提示（建议改进）           N 个
───────────────────────────────
| # | 文件:行号 | 类型 | 问题 | 修复建议 |
|---|----------|------|------|---------|

✅ 安全检查项                 N 个
───────────────────────────────
列出通过检查的项目

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总结：[一句话概括安全状况]
```

---

## 注意事项

- 🔴 **严重**：API Key 泄露、SQL 注入、未授权访问 → 必须立即修复
- 🟡 **警告**：存在风险但利用条件较苛刻 → 建议尽快修复
- 🟢 **提示**：不直接造成危害，但不符合最佳实践 → 可以改进
- **本项目特点**：企业级 RAG 知识库系统，涉及 LLM 调用（API Key 保护重要）、用户数据（权限校验重要）、文件上传（路径遍历风险）
- 所有发现必须附带**具体文件路径和行号**，方便快速定位
- 修复建议要**具体可操作**，不写笼统的"增强安全性"
- 特别注意：`.env` 中的 `DASHSCOPE_API_KEY` 绝对不能提交到 Git
