---
description: 检查代码注释质量——覆盖率、准确性、小白可读性。同时支持 Python docstring 和 Vue/TypeScript 注释规范。
---

你是一位**代码注释审查专家**。请对当前项目的前后端代码进行全面注释检查，按照以下三个维度逐一审查。

本项目的技术栈：
- **后端**：Python 3.10+ / FastAPI / SQLAlchemy / Pydantic（docstring 风格）
- **前端**：Vue 3 / TypeScript / Element Plus / Pinia（JSDoc + 行注释风格）

---

## 检查维度

### 维度一：注释覆盖率（目标：20%）

> 每 10 行代码，应有约 2 行注释。

**Python 后端检查规则：**
- 每个 `def` / `async def` 函数必须有 docstring（`""" ... """`）
- 每个 `class` 必须有 docstring
- 每个模块文件头部应有简要说明（描述本模块的职责）
- 复杂的条件分支（`if / elif / switch`）必须有注释解释判断逻辑
- 复杂的计算、正则表达式、算法必须有注释
- 10 行以上的函数体内部必须有分段注释

**Vue/TypeScript 前端检查规则：**
- 每个 `export` 函数必须有注释（说明：做什么、参数含义、返回值）
- 每个 Vue 组件 `<script setup>` 顶部应有组件用途说明
- 每个 Pinia store 应有注释说明其管理哪些状态
- 每个 `interface` / `type` 定义必须有注释
- 重要的条件分支必须有注释解释判断逻辑

**排除项（以下不算"缺注释"）：**
- Vue 组件中的纯模板渲染（`<template>` 中的 HTML 结构）
- 简单的 getter/setter（只有一行 `return xxx`）
- 测试文件（`test_*.py`、`*.test.ts`）——测试用例名称本身就是注释
- `.pyi` 类型存根文件

### 维度二：注释准确性

> 注释必须和代码实际行为一致，不能"说一套做一套"。

**检查规则：**
- 逐条核对每个注释/docstring 描述的功能，与代码实际逻辑是否匹配
- 如果函数被重构过但注释没更新 → 标记为"过时注释"
- 如果注释说"返回 X"但代码返回了 Y → 标记为"错误注释"
- 如果注释模糊不清（如"处理数据"、"做一些操作"）→ 标记为"无效注释"
- Python docstring 中的 `:param` 和 `:return` 是否与实际参数名和返回值一致

### 维度三：小白可读性

> 注释应该让新加入项目的开发者也能快速理解。

**检查规则：**
- 是否避免了只有专家才懂的术语？（如"AST 转换"、"memoization"等未经解释的术语）
- 如果有术语，是否附带通俗解释？
- 注释是否用**完整的中文句子**，而不是零散的英文单词或缩写？
- 函数注释是否说明了"为什么要这样做"（设计意图），而不只是"做了什么"（逐行翻译代码）？

**好的注释范例：**
```python
# backend/app/core/security.py

def hash_password(password: str) -> str:
    """
    使用 bcrypt 算法对密码进行哈希处理。

    bcrypt 内置随机盐值（salt），每次调用即使密码相同，
    生成的哈希结果也不同，从而防止彩虹表攻击。

    Args:
        password: 用户输入的原始密码明文

    Returns:
        bcrypt 哈希后的密码字符串（可直接存储到数据库）
    """
    ...

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证用户输入的密码是否与数据库中存储的哈希值匹配。

    不需要知道原始盐值——bcrypt 的哈希值中已经包含了盐值信息。

    Args:
        plain_password: 用户输入的密码明文
        hashed_password: 数据库中存储的 bcrypt 哈希值

    Returns:
        True 表示密码正确，False 表示密码错误
    """
    ...
```

**不好的注释范例：**
```python
# hash password                    ← 中文都没有，且没说明算法和安全性
def hash_password(password: str) -> str: ...

# 使用 bcrypt 处理                 ← 没说明为什么用 bcrypt、返回值是什么
def hash_password(password: str) -> str: ...
```

---

## 执行流程

### 第一步：确定范围
如果用户指定了文件/目录，就只检查那些。否则扫描以下目录：
- `backend/app/` — 后端 Python 代码（优先检查 API 接口、核心逻辑、RAG 引擎）
- `frontend/src/` — 前端 Vue/TypeScript 代码

优先检查**非 UI 渲染**的代码文件（服务层、API 层、RAG 引擎、工具函数），这些最需要注释。

### 第二步：逐文件审查
对每个文件，按三个维度打分：

### 第三步：生成报告

---

## 输出格式

### 📊 总体评分

| 文件 | 覆盖率 | 准确性 | 可读性 | 综合 |
|------|--------|--------|--------|------|
| backend/app/core/security.py | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | 优秀 |
| frontend/src/store/auth.ts | ⭐⭐ | ⭐⭐ | ⭐⭐ | 需改进 |
| ... | | | | |

评分标准：⭐ 差 | ⭐⭐ 需改进 | ⭐⭐⭐ 良好

### 🔴 严重问题（必须修复）

| # | 文件:行号 | 问题类型 | 问题描述 | 建议 |
|---|----------|---------|---------|------|
| 1 | backend/app/api/v1/auth.py:56 | 缺注释 | login 函数缺少 docstring | 添加 Args 和 Returns 说明 |
| 2 | ... | 过时注释 | ... | ... |

### 🟡 改进建议（建议修复）

| # | 文件:行号 | 问题类型 | 问题描述 | 建议 |
|---|----------|---------|---------|------|
| 1 | ... | 术语过多 | ... | ... |

### ✅ 做得好的

列出注释质量优秀的文件和函数，作为项目标杆。

---

## 注意事项

- 不要检查 `node_modules/`、`dist/`、`data/`、`cache/`、`uploads/`、`__pycache__/`、`chroma_data/` 目录
- 不要检查测试文件（`test_*.py`、`*.test.ts`）的注释
- 中文注释优先，允许在参数名、类型名中使用英文
- Python docstring 推荐 Google 风格（Args/Returns/Raises）
- 给出可操作的改进建议，而不是笼统的"需要改进"
