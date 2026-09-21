---
description: 启动企业员工自助服务系统（前后端同时启动）
---

请启动企业员工自助服务系统。本系统包含前端（Vue 3 + Vite）和后端（Python FastAPI），需要分别启动：

## 启动方式

### 方式一：一键启动（推荐）
```bash
cmd.exe /c "E:\Claude_Project_third\Enterprise Employee Self-Service Intelligent Knowledge Base\start_all.bat"
```

### 方式二：分别启动

**后端：**
```bash
cd "E:\Claude_Project_third\Enterprise Employee Self-Service Intelligent Knowledge Base\backend" && python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

**前端：**
```bash
cd "E:\Claude_Project_third\Enterprise Employee Self-Service Intelligent Knowledge Base\frontend" && npm run dev
```

## 启动后访问

- **前端页面**：http://localhost:5173
- **后端 API 文档**：http://localhost:8001/docs
- **健康检查**：http://localhost:8001/api/health

## 默认管理员账号

- 用户名和密码见 `backend/.env` 中的 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD`

## 故障排查

- 如果前端启动失败，检查 `node_modules/` 是否存在，否则运行 `npm install`
- 如果后端启动失败，检查 Python 依赖是否安装：`pip install -r backend/requirements.txt`
- 如果 API 调用 401 错误，检查 `.env` 中的 JWT Secret 是否正确配置
- 如果 LLM 调用失败，检查 `.env` 中的 `DASHSCOPE_API_KEY` 是否有效
