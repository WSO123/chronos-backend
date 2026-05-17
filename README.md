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

本地默认关闭真实 LLM，Today 使用 Planning Engine v1 + mock Daily Planner Agent shell：

```env
AI_ENABLE_REAL_LLM=false
LLM_PROVIDER=mock
LLM_MODEL=structured-mock-v1
LLM_FALLBACK_PROVIDER=mock
LLM_ALLOWED_PROVIDERS=openai,openai-compatible
LLM_ALLOWED_MODELS=gpt-4.1-mini
LLM_MAX_OUTPUT_TOKENS=800
```

真实 provider 需要显式开启，不能让 LLM 绕过业务层校验或用户确认：

```env
AI_ENABLE_REAL_LLM=true
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
LLM_API_KEY=...
LLM_BASE_URL=
LLM_FALLBACK_PROVIDER=mock
LLM_ALLOWED_PROVIDERS=openai
LLM_ALLOWED_MODELS=gpt-4.1-mini
LLM_MAX_OUTPUT_TOKENS=800
```

真实 provider smoke 默认不会进入本地验证链路；需要手动显式允许：

```bash
uv run python scripts/smoke_llm_provider.py
AI_ENABLE_REAL_LLM=true LLM_PROVIDER=openai LLM_MODEL=gpt-4.1-mini LLM_ALLOWED_MODELS=gpt-4.1-mini LLM_API_KEY=... uv run python scripts/smoke_llm_provider.py --allow-real-llm
```

真实 provider 手动验收需要按模板记录 model、usage、prompt checksum、JSONL compare 和最终结论：

```text
docs/llm-provider-acceptance/TEMPLATE.md
```

执行数据库迁移：

```bash
uv run alembic upgrade head
```

创建本地开发用户，并复制输出的 `X-User-Id` 到后续 API 请求头。本地默认 `AUTH_MODE=dev_header`；生产 / 准生产环境应使用 `AUTH_MODE=jwt` 和 `Authorization: Bearer <access_token>`，不要继续信任开发态 header。

```bash
uv run python scripts/dev_seed_user.py
```

正式 token 闭环已提供：

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
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

跑一遍核心 AI 主线 smoke 验证：

```bash
uv run python scripts/smoke_core_ai_mainline.py
```

跑一遍 Planning Engine 固定场景评估：

```bash
uv run python scripts/evaluate_planning_engine.py
uv run python scripts/evaluate_planning_engine.py --jsonl-output /tmp/chronos-planner-eval.jsonl
uv run python scripts/compare_planner_eval_jsonl.py /tmp/chronos-planner-eval-baseline.jsonl /tmp/chronos-planner-eval-candidate.jsonl
uv run python scripts/check_planner_eval_policy.py /tmp/chronos-planner-eval.jsonl
uv run python scripts/smoke_daily_planner_fallback.py
uv run python scripts/generate_llm_acceptance_dry_run.py --date 2026-05-17
uv run python scripts/generate_llm_acceptance_record.py --smoke-json /tmp/chronos-llm-smoke.json --fallback-json /tmp/chronos-llm-fallback.json --compare-json /tmp/chronos-planner-compare.json --policy-json /tmp/chronos-planner-policy.json --output docs/llm-provider-acceptance/YYYY-MM-DD-provider-model-purpose.md
```

也可以用统一验证入口跑基础检查和指定 smoke：

```bash
uv run python scripts/verify_local.py --smoke p3
uv run python scripts/verify_local.py --smoke ai-mainline
uv run python scripts/verify_local.py --smoke llm-fallback
uv run python scripts/verify_local.py --planner-eval
uv run python scripts/verify_local.py --planner-eval-policy
```

这些 smoke 会通过 API 跑通：

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Daily Report -> Me
P2: Goals -> Goal Detail / Timeline -> Reports / Insights -> Me
P3: Data Source -> Capture / Inbox -> Today -> Energy -> Reminder Center -> Scheduler
AI Mainline: Capture Parser -> Daily Planner -> Strategy Explanation -> Task Breakdown -> Daily Report -> Insight Detail
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
│   ├── ai/                 # AI Agent / prompt registry / provider / structured output schema
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

`scripts/dev_seed_demo.py` 用于前端和手动体验，默认创建 `demo@chronos.local` 用户并输出开发态 `X-User-Id`。
`scripts/smoke_p1_execution_loop.py` 用于开发后快速防回归，每次默认创建一个独立 smoke 用户，不会重置数据库。
`scripts/smoke_p2_goal_insight_loop.py` 用于验证 P2 Goals / Reports / Insights 合同，每次默认创建一个独立 smoke 用户，不会重置数据库。
`scripts/smoke_p3_natural_growth_loop.py` 用于验证 P3 数据接入、精力、外部输入、提醒、Me 入口状态和调度契约，每次默认创建一个独立 smoke 用户，不会重置数据库。
`scripts/smoke_core_ai_mainline.py` 用于验证核心 bounded agents 主线：Capture Parser、Daily Planner、Strategy Explanation、Task Breakdown、Daily Report、Insight Detail 都被调用并写入 `AIJob`，每次默认创建一个独立 smoke 用户，不会重置数据库。
`scripts/evaluate_planning_engine.py` 用于验证 Planning Engine 的固定场景排序、容量、Energy、依赖、用户修正、行为反馈、Goal 价值和超期 Goal 恢复，使用测试数据库，不污染开发数据库；可选 `--jsonl-output` 会写出离线评估记录，便于后续比较 provider / prompt。
`scripts/compare_planner_eval_jsonl.py` 用于比较两份 Planning Engine eval JSONL，输出 scenario 通过状态、排序、容量和 `item_signals` 差异；默认只报告结果，`--fail-on-regression` 可作为显式手动 gate。
`scripts/check_planner_eval_policy.py` 用于把一次 Planning Engine eval JSONL 与 [planner eval golden baseline](./docs/planner-eval-baselines/README.md) 对齐，识别缺失场景、失败场景、字段丢失和 baseline 变更。
`scripts/smoke_daily_planner_fallback.py` 用于验证 Daily Planner provider 失败时 Today / Strategy 仍能走 Planning Engine fallback，不调用真实 provider。
`scripts/generate_llm_acceptance_dry_run.py` 用于生成 synthetic provider smoke / fallback / compare / policy JSON，并产出一份 dry-run 验收草稿，帮助接真实 provider 前先跑通验收流程。
`scripts/generate_llm_acceptance_record.py` 用于把真实 provider smoke、fallback smoke、planner eval compare 和 golden policy check 的 JSON 输出汇总成 Markdown 验收草稿，默认脱敏 provider response id。
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

1.  在 `app/ai/schemas/` 定义 structured output schema。
2.  在 `app/ai/prompts/` 增加版本化 prompt，并注册到 prompt registry。
3.  在 `app/ai/agents/` 定义普通 Agent function；只有多步骤、有状态、需要循环反思时再升级为 LangGraph。
4.  在 service 层调用 Agent 并校验输出，禁止 Agent 直接写业务表。
5.  需要异步执行时，再在 `app/workers/tasks.py` 注册 Celery Task，并通过 API 触发。

##  注意事项

*   **MinIO 访问**: 本地 MinIO 控制台地址为 `http://localhost:9001` (账号/密码: `minioadmin`/`minioadmin`)。
*   **首次运行**: `pgvector` 扩展会在数据库容器首次启动时自动加载。
