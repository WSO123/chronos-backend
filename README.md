# Chronos Backend AI - 后端

这是一个基于 **FastAPI + LangGraph** 的后端系统。

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
note-backend/
├── app/
│   ├── api/                # 接口层：处理 HTTP 请求，不做复杂逻辑
│   ├── core/               # 核心层：全局配置、数据库连接、Celery 配置
│   ├── services/           # 服务层：业务逻辑封装 (如 S3 上传、RAG 检索)
│   ├── workers/            # 任务层：Celery 任务定义 & AI Agent 实现
│   │   └── agents/         # LangGraph 工作流定义 (核心 AI 逻辑)
│   └── models/             # 数据模型 (SQLModel/SQLAlchemy)
├── docker-compose.yml      # 基础设施编排
├── pyproject.toml          # 依赖管理配置
└── uv.lock                 # 依赖版本锁定
```

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
