# Chronos Engineering Guidelines

> 本文定义 Chronos 后端工程开发规范，用于约束后续代码结构、模块边界、数据写入、API 设计、AI 接入和测试策略。  
> 它是工程层面的约束文档，服务于 Chronos 的产品目标：轻盈、克制、可信、可执行。

---

## 1. 核心原则

Chronos 后端不是普通 CRUD 项目，而是每日执行系统。

工程实现必须服务以下原则：

- 以 `Capture -> Inbox -> Today -> Task Detail -> Focus -> Report` 为主线。
- 业务规则放在 service，不散落在 router / worker / model 中。
- 关键用户行为必须事件化。
- AI 只产生结构化建议，不直接写业务表。
- 页面接口默认返回少而准的信息。
- P1 优先跑通闭环，不追求功能铺满。

### 1.1 运行时版本

- Python 版本以仓库根目录 `.python-version` 为准。
- `pyproject.toml` 的 `requires-python` 必须与 `.python-version` 保持兼容。
- CI 必须读取 `.python-version`，避免本地和远端解释器版本漂移。

---

## 2. 目录结构规范

推荐结构：

```text
app/
  api/
    v1/
      captures.py
      inbox.py
      tasks.py
      goals.py
      today.py
      focus.py
      reports.py
      me.py
      ai_jobs.py
      router.py

  ai/
    agents/
      daily_planner.py
    prompts/
      registry.py
      daily_planner/
        p2-daily-planner-agent-v1.md
    providers/
      base.py
      mock.py
      registry.py
    schemas/

  core/
    config.py
    db.py
    celery.py
    security.py

  models/
    user.py
    goal.py
    task.py
    task_step.py
    activity_event.py
    capture.py
    inbox.py
    daily_plan.py
    plan_revision.py
    strategy_snapshot.py
    focus_session.py
    report.py
    ai_job.py

  schemas/
    captures.py
    inbox.py
    tasks.py
    goals.py
    today.py
    focus.py
    reports.py
    me.py
    ai_jobs.py

  services/
    capture_service.py
    inbox_service.py
    task_service.py
    goal_service.py
    planning_service.py
    focus_service.py
    report_service.py
    ai_job_service.py
    activity_event_service.py

  workers/
    tasks.py
```

### 2.1 api/

职责：

- 声明路由。
- 接收 request。
- 调用 service。
- 返回 response schema。

禁止：

- 直接写数据库。
- 直接调用 LLM。
- 堆业务规则。
- 在 router 中处理复杂状态流转。

### 2.2 services/

职责：

- 承载业务规则。
- 管理状态流转。
- 写入 ActivityEvent。
- 管理事务边界。
- P1 直接使用 db session 访问数据；如后续引入 repository 层，必须先更新本规范和后端架构文档。

Service 是后端业务逻辑的核心层。

### 2.3 models/

职责：

- SQLAlchemy ORM 模型。
- 数据表字段。
- 关系定义。

禁止：

- 在 model 中写复杂业务逻辑。
- 在 model 中调用外部服务。

### 2.4 schemas/

职责：

- Pydantic request / response schema。
- API 输入输出约束。

注意：

- 不要直接把 ORM model 暴露给前端。
- 页面聚合接口应该有专门 response schema。

### 2.5 ai/

职责：

- LLM provider adapter。
- structured output schema。
- prompt 文件。
- AI client。

禁止：

- 在 provider 中写业务表。
- 在 prompt 中编码不可追踪业务规则。

### 2.6 workers/

职责：

- Celery task。
- Agent 调度。
- AIJob 状态更新。

禁止：

- Worker 绕过 service 直接乱写业务表。
- Worker 里复制 service 的业务规则。

---

## 3. 分层调用规则

推荐调用方向：

```text
api -> service -> model/db
api -> service -> ai_job -> celery worker -> agent -> llm adapter
worker -> service -> model/db
```

禁止反向依赖：

- model 不依赖 service。
- service 不依赖 api。
- provider 不依赖 service。
- prompt 不依赖业务代码。

关键规则：

- API 不直接调用 LLM。
- API 不直接写 DB。
- Worker 不绕过 service 修改核心业务表。
- LLM 不直接写业务表。
- Service 不绑定具体 LLM provider。

---

## 4. 数据模型规范

### 4.1 基础字段

核心业务表默认包含：

```text
id
created_at
updated_at
```

用户相关表默认包含：

```text
user_id
```

P1 即使是单用户开发模式，也保留 `user_id`。

### 4.2 状态字段

状态字段必须使用明确枚举，不使用随意字符串。

示例：

```text
Task.status = active | in_focus | completed | postponed | archived
AIJob.status = queued | running | succeeded | succeeded_with_fallback | failed | canceled
```

### 4.3 删除策略

默认使用软删除 / archived 状态。

除非明确说明，不做 hard delete。

### 4.4 时间和时区

所有数据库时间建议使用 UTC。

DailyPlan / DailyReport 必须按用户本地日期切分。

实现时需要明确：

- 用户 timezone 存在哪里。
- `plan_date` 使用用户本地日期。
- `created_at/updated_at` 使用 UTC timestamp。

### 4.5 事件化要求

以下动作必须写入 `ActivityEvent`：

- 创建任务
- 编辑任务
- 完成任务
- 延后任务
- 中断任务
- 拆解任务
- 开始 Focus
- 完成 Focus
- 中断 Focus
- 创建 DailyPlan
- Replan
- 用户接受 / 忽略 / 修改 AI 建议

状态字段用于当前查询，事件用于复盘、学习和审计。

---

## 5. API 设计规范

### 5.1 页面聚合接口与资源接口分离

页面聚合接口：

```text
GET /api/v1/today
GET /api/v1/me/overview
GET /api/v1/reports/daily/{date}
```

资源接口：

```text
GET /api/v1/tasks/{id}
POST /api/v1/tasks/{id}/complete
POST /api/v1/focus-sessions
```

规则：

- 页面聚合接口服务体验。
- 资源接口服务具体操作。
- 不要让前端拼大量底层资源来渲染核心页面。

### 5.2 Today 接口

`GET /today` 必须保持克制。

默认返回：

- strategy summary
- 推荐任务序列
- 今日进度
- quick actions

默认不返回：

- 完整 score factors
- 全量历史事件
- 大量洞察图表
- 复杂策略配置

### 5.3 Task Detail 接口

`GET /tasks/{id}` 只返回执行前必要信息。

历史事件使用：

```text
GET /api/v1/tasks/{id}/events
```

### 5.4 Focus 接口

Focus API 只围绕执行状态：

- start
- complete
- interrupt
- postpone

P1 不实现 pause。

### 5.5 错误响应

错误响应应统一结构：

```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "Task not found",
    "details": {}
  }
}
```

### 5.6 分页和过滤

列表接口默认支持：

- `limit`
- `offset` 或 cursor
- 必要过滤条件

P1 可以先使用 `limit/offset`。

---

## 6. Service 设计规范

Service 方法应该表达业务动作，而不是数据库操作。

推荐：

```python
task_service.complete_task(...)
focus_service.complete_focus_session(...)
planning_service.create_daily_plan(...)
inbox_service.confirm_inbox_item(...)
```

不推荐：

```python
task_service.update(...)
task_service.save(...)
service.do_stuff(...)
```

### 6.1 事务

同一个业务动作中，状态更新和 ActivityEvent 写入必须在同一事务中完成。

示例：

```text
complete task:
  update Task.status
  update DailyPlanItem.status
  insert ActivityEvent
  commit
```

### 6.2 状态流转

状态流转必须在 service 中校验。

示例：

- completed 任务不能再次 start focus。
- archived 任务不能进入 Today。
- active FocusSession 才能 complete / interrupt。

### 6.3 返回值

Service 返回业务对象或明确 DTO，不直接返回未处理的 ORM 给 API。

---

## 7. AI / LLM 开发规范

详见：

[Chronos LLM & Agent Architecture](./chronos-llm-agent-architecture.md)

核心要求：

- 所有 AI 任务创建 AIJob。
- LLM 输出必须 structured output。
- 输出必须经过 Pydantic validation。
- 失败必须有 fallback。
- LLM 不直接写业务表。
- Prompt 文件必须版本化。
- 真实 provider 必须显式开关，默认本地和 CI 使用 mock。
- 不在普通日志里输出用户隐私内容。

### 7.1 AIJob

AIJob 必须记录：

- provider
- model
- prompt_version
- latency_ms
- error_message
- retry_count
- metadata

### 7.2 Prompt

Prompt 放在：

```text
app/ai/prompts/
```

不要散落在 service、worker 或 agent 代码字符串中。

要求：

- Agent 通过 prompt registry 按 key 获取 prompt。
- Prompt 文件必须包含目标、输入说明、输出 schema、产品语气和禁止事项。
- Prompt version 必须进入 `AIJob.prompt_version`。
- Prompt checksum 必须进入 `AIJob.job_metadata`。
- 修改 prompt 时必须同步迭代文档和相关测试。

---

## 8. 测试规范

### 8.1 优先测试 service

业务规则优先写 service 测试。

必须覆盖：

- 状态流转
- ActivityEvent 写入
- DailyPlan 生成
- Focus 完成 / 中断 / 延后
- Inbox confirm

### 8.2 API 测试

API 测试覆盖：

- happy path
- 404 / 400 / invalid state
- user_id 隔离
- response schema

### 8.3 AI 测试

AI 测试默认用 mock provider。

必须覆盖：

- structured output validation
- fallback
- AIJob 状态流转
- retry

涉及真实 provider adapter 时，必须覆盖：

- 默认关闭真实 LLM 时仍返回 mock provider
- provider 调用参数和 structured schema
- 内部 `mock_output` / prompt trace 不发送给真实 provider
- provider 错误统一包装为 `LLMProviderError`
- service fallback 时 `AIJob.provider` / `AIJob.model` 记录实际选中的 provider
- service fallback 时记录 `latency_ms`、`failure_type` 和 root error type

涉及 Daily Planner Agent / Planning Engine 时，必须覆盖：

- mock provider structured output
- Agent 失败 fallback
- Agent 输出不合法 fallback
- `AIJob(job_type=daily_planner)` 可通过 Strategy Detail source 追踪
- `AIJob.latency_ms` / `job_metadata.provider_latency_ms` / `job_metadata.usage` 结构稳定
- Planning Engine evaluation 不退化

### 8.4 Migration 测试

模型变更必须有 Alembic migration。

Migration 至少要能在本地数据库上 upgrade 成功。

### 8.5 Smoke 与验证阶梯

每次迭代完成后，按改动范围选择验证阶梯：

```bash
uv run python -m unittest discover -s tests
uv run python -m compileall app tests scripts
git diff --check
```

也可以使用统一入口执行基础验证：

```bash
uv run python scripts/verify_local.py
```

涉及数据库模型、索引、枚举或 migration 时，必须额外执行：

```bash
uv run alembic upgrade head
```

涉及核心执行闭环时，至少执行：

```bash
uv run python scripts/smoke_p1_execution_loop.py
```

涉及 P2 Goals / Strategy / Insights / Reports 时，额外执行：

```bash
uv run python scripts/smoke_p2_goal_insight_loop.py
```

涉及 Planning Engine 排序、容量、Energy 适配、Strategy factors 或评分权重时，额外执行：

```bash
uv run python scripts/evaluate_planning_engine.py
```

涉及 Daily Planner Agent shell 或 LLM provider 时，额外执行：

```bash
uv run python -m unittest tests.test_daily_planner_agent tests.test_today_services tests.test_today_api
```

涉及真实 provider 手动验证时，只能在显式允许后执行，不纳入默认 CI / verify_local：

```bash
uv run python scripts/smoke_llm_provider.py
AI_ENABLE_REAL_LLM=true LLM_PROVIDER=openai LLM_MODEL=gpt-4.1-mini LLM_API_KEY=... uv run python scripts/smoke_llm_provider.py --allow-real-llm
```

或通过统一验证入口追加：

```bash
uv run python scripts/verify_local.py --planner-eval
```

涉及 P3 数据接入、精力、外部输入、提醒、Me 入口状态、调度 worker 或 notification 时，额外执行：

```bash
uv run python scripts/smoke_p3_natural_growth_loop.py
```

需要完整 smoke 梯度时，可执行：

```bash
uv run python scripts/verify_local.py --all-smoke
```

Smoke 脚本约束：

- 必须创建独立 smoke 用户，不重置开发数据库。
- 必须走公开 API 或已注册 worker task，不直接篡改业务状态。
- 必须验证产品主路径，而不是只检查内部函数能运行。
- 必须保持克制，不为了 smoke 引入只服务测试的业务字段。

### 8.6 CI 验证边界

GitHub Actions 默认只执行基础验证：

```bash
uv run python scripts/verify_local.py
```

说明：

- CI 不默认执行 P1/P2/P3 smoke，避免缺少本地开发数据库、worker 或外部服务时误报。
- 涉及 smoke 覆盖面的迭代，仍必须在本地按影响范围显式执行对应 smoke。
- 如果后续 CI 增加 Postgres / Redis service containers，再把 smoke 分阶段接入。

---

## 9. 文档同步规范

以下变更必须同步文档：

- 新增 / 修改 API
- 新增 / 修改数据模型
- 新增 / 修改状态机
- 新增 / 修改 ActivityEvent
- 新增 / 修改 AI Agent
- 修改 P1/P2/P3/P4 分期边界
- 修改核心交互路径

进入开发前必须有迭代文档：

[Iteration Docs](./iterations/README.md)

---

## 10. 禁止事项

严禁：

- 在 router 中堆业务逻辑。
- 在 router 中直接写 DB。
- 在 router 中直接调用 LLM。
- 让 LLM 直接写业务表。
- 绕过 service 修改核心状态。
- 修改任务状态但不写 ActivityEvent。
- 把 Today 接口做成大杂烩。
- 把 Task Detail 做成信息仓库。
- 把 Focus 做成控制面板。
- P1 过早引入项目管理、社交、健康、日历自动排程等复杂能力。
- 在普通日志中输出用户隐私输入。
- 为了技术炫技引入不必要抽象。

---

## 11. P1 开发优先级

P1 开发应该按以下顺序推进：

1. 工程基础：`.gitignore`、Alembic、router 结构、基础配置。
2. 核心模型：User、UserSettings、Goal、Task、TaskStep、ActivityEvent、AIJob。
3. Task / Light Goal API。
4. Capture / Inbox。
5. DailyPlan / Today。
6. FocusSession。
7. DailyReport / Me Overview。
8. AI mock / fallback。
9. 真实 LLM adapter。

---

## 12. 一句话原则

```text
Chronos 的工程实现要把复杂度留在系统内部，
把稳定、克制、可执行的体验交给用户。
```
