# Chronos Backend - 后端

这是 Chronos AI Execution OS 的后端系统，基于 **FastAPI + SQLAlchemy + Celery** 构建。

##  项目亮点与架构哲学

本架构专为**生产级 AI 应用**设计，遵循 "Async-First"（异步优先）和 "Keep It Simple"（极简主义）原则。

### 技术栈选型

| 模块 | 技术 | 核心优势 |
| :--- | :--- | :--- |
| **API 框架** | **FastAPI** | 现代化、异步高性能、自动生成 API 文档。 |
| **包管理** | **uv** | 极速的 Python 包管理工具（Rust 编写），秒级环境构建。 |
| **异步任务** | **Celery + Redis** | 确保所有耗时 AI 生成任务不阻塞主线程。 |
| **AI 编排** | **LangGraph** | 处理复杂的循环工作流（如“反思-修改”），支持状态持久化。 |
| **数据库** | **PostgreSQL + pgvector** | "All-in-One" 方案，同时处理业务数据和向量检索，无需维护独立的 Vector DB。 |
| **对象存储** | **MinIO** | S3 兼容协议，实现文件存储与应用解耦，方便未来迁移至云存储。 |

##  快速开始

本项目使用现代化工具链，只需几步即可启动。

### 前置要求

*   [Docker](https://www.docker.com/) & Docker Compose
*   [uv](https://docs.astral.sh/uv/) (Python 极速包管理器)
*   Python 版本以 `.python-version` 为准，当前为 3.14

### 1. 启动基础设施

一键拉起 PostgreSQL (带向量插件), Redis 和 MinIO。

```bash
docker compose up -d
```

### 2. 环境配置与依赖安装

复制环境变量模版（已预设为本地开发配置）：

```bash
cp .env.example .env  # 如果没有 .env.example，直接使用 .env 即可
```

使用 `uv` 极速同步依赖：

```bash
uv sync
```

### 3. 启动服务

执行数据库迁移：

```bash
uv run alembic upgrade head
```

创建本地开发用户，并复制输出的 `X-User-Id` 到后续 API 请求头：

```bash
uv run python scripts/dev_seed_user.py
```

准备一组可用于前端联调和手动验收的 P1 demo 数据：

```bash
uv run python scripts/dev_seed_demo.py
```

跑一遍 P1 主链路 smoke 验证：

```bash
uv run python scripts/smoke_p1_execution_loop.py
```

跑一遍 P2 目标 / 洞察 smoke 验证：

```bash
uv run python scripts/smoke_p2_goal_insight_loop.py
```

跑一遍 P3 自然生长 smoke 验证：

```bash
uv run python scripts/smoke_p3_natural_growth_loop.py
```

跑一遍 Planning Engine 固定场景评估：

```bash
uv run python scripts/evaluate_planning_engine.py
```

也可以用统一验证入口跑基础检查和指定 smoke：

```bash
uv run python scripts/verify_local.py --smoke p3
uv run python scripts/verify_local.py --planner-eval
```

这些 smoke 会通过 API 跑通：

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Daily Report -> Me
P2: Goals -> Goal Detail / Timeline -> Reports / Insights -> Me
P3: Data Source -> Capture / Inbox -> Today -> Energy -> Reminder Center -> Scheduler
```

**启动 API 后端 (热重载模式):**

```bash
uv run uvicorn main:app --reload
```

*   API 文档地址: http://localhost:8000/docs
*   健康检查: http://localhost:8000/health

**启动 AI 任务 Worker:**

```bash
uv run celery -A app.core.celery.celery_app worker --loglevel=info
```

##  项目结构说明

```text
chronos-backend/
├── app/
│   ├── api/                # 接口层：处理 HTTP 请求，不做复杂逻辑
│   ├── core/               # 核心层：全局配置、数据库连接、Celery 配置
│   ├── models/             # 数据模型 (SQLAlchemy)
│   ├── schemas/            # API 输入输出结构
│   ├── services/           # 服务层：业务逻辑、调度、报表、AIJob 状态
│   └── workers/            # 任务层：Celery 任务定义与后续 Agent 入口
├── docs/                   # 产品、架构、迭代规范与迭代记录
├── scripts/                # 本地开发 seed / smoke 工具
├── tests/                  # 服务层和 API 层测试
├── docker-compose.yml      # 基础设施编排
├── pyproject.toml          # 依赖管理配置
└── uv.lock                 # 依赖版本锁定
```

## P1-P3 主链路验收

本阶段优先保护 Chronos 的核心执行闭环，不追求复杂驾驶舱：

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report / Me
```

本地验收建议按顺序执行：

```bash
uv run alembic upgrade head
uv run python scripts/dev_seed_demo.py
uv run python scripts/smoke_p1_execution_loop.py
uv run python scripts/smoke_p2_goal_insight_loop.py
uv run python scripts/smoke_p3_natural_growth_loop.py
uv run python scripts/evaluate_planning_engine.py
uv run python -m unittest discover -s tests
uv run python -m compileall app tests scripts
git diff --check
```

`scripts/dev_seed_demo.py` 用于前端和手动体验，默认创建 `demo@chronos.local` 用户并输出 `X-User-Id`。
`scripts/smoke_p1_execution_loop.py` 用于开发后快速防回归，每次默认创建一个独立 smoke 用户，不会重置数据库。
`scripts/smoke_p2_goal_insight_loop.py` 用于验证 P2 Goals / Reports / Insights 合同，每次默认创建一个独立 smoke 用户，不会重置数据库。
`scripts/smoke_p3_natural_growth_loop.py` 用于验证 P3 数据接入、精力、外部输入、提醒、Me 入口状态和调度契约，每次默认创建一个独立 smoke 用户，不会重置数据库。
`scripts/evaluate_planning_engine.py` 用于验证 Planning Engine 的固定场景排序、容量和 Energy 行为，使用测试数据库，不污染开发数据库。
`scripts/verify_local.py` 用于编排本地验证阶梯，例如 `uv run python scripts/verify_local.py --all-smoke --planner-eval`。

前端联调接口契约见：

```text
docs/chronos-p1-frontend-api-contract.md
docs/chronos-p2-frontend-api-contract.md
docs/chronos-p3-frontend-api-contract.md
```

## CI

GitHub Actions 会在 push / pull request 上执行基础验证：

```bash
uv run python scripts/verify_local.py
```

Smoke 仍按改动范围在本地显式执行，避免 CI 在没有本地开发数据库和 worker 环境时误报。

##  开发指南

### 添加新依赖

不再使用 `pip install`，请使用 `uv add`：

```bash
uv add pandas
```

### 创建新的 AI Agent

1.  在 `app/workers/agents/` 下定义你的 LangGraph StateGraph。
2.  在 `app/workers/tasks.py` 中注册一个新的 Celery Task 来调用这个 Graph。
3.  在 `app/api/` 中添加一个 Endpoint 来触发这个 Task。

##  注意事项

*   **MinIO 访问**: 本地 MinIO 控制台地址为 `http://localhost:9001` (账号/密码: `minioadmin`/`minioadmin`)。
*   **首次运行**: `pgvector` 扩展会在数据库容器首次启动时自动加载。
