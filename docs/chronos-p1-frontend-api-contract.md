# Chronos P1 Frontend API Contract

> 版本：v1
> 日期：2026-05-16
> 适用范围：P1 backend -> frontend handoff

---

## 1. 文档目的

这份文档把当前后端能力按 Chronos 的前端页面和核心用户路径整理出来，供前端开发、联调和后续迭代对齐使用。

P2 已完成能力的集中合同见：[Chronos P2 Frontend API Contract](./chronos-p2-frontend-api-contract.md)。

Bearer token 版 P1 本地联调 walkthrough 见：[Chronos P1 Bearer API Walkthrough](./chronos-p1-bearer-api-walkthrough.md)。

登录、注册、refresh 和错误码处理建议见：[Chronos Auth MVP Frontend Handling](./chronos-auth-mvp-frontend-handling.md)。

Chronos P1 的主路径是：

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Daily Report -> Me
```

接口设计要服务一个产品判断：前端默认呈现清晰、轻量、可行动的信息，不把 AI 中间过程、调度细节和报表解释堆给用户。

---

## 2. 全局约定

### Base URL

```text
/api/v1
```

本地开发：

```text
http://localhost:8000/api/v1
```

### Auth / User Context

本地开发默认使用开发态用户上下文，所有业务接口都必须传：

```http
X-User-Id: <user_uuid>
```

生产或准生产环境必须改用 Bearer access token：

```http
Authorization: Bearer <access_token>
```

后端通过 `AUTH_MODE` 控制认证模式：

- `AUTH_MODE=dev_header`：仅用于本地开发，读取 `X-User-Id`。当 `ENVIRONMENT=production` 或 `ALLOW_DEV_AUTH_HEADER=false` 时会失败关闭。
- `AUTH_MODE=jwt`：读取 `Authorization: Bearer ...`，并校验 token subject 对应的用户存在且 `is_active=true`。此模式不会接受 `X-User-Id` 作为认证凭据；production 环境下 `SECRET_KEY` 不能保留默认值。

本地可通过以下命令创建用户和 demo 数据：

```bash
uv run python scripts/dev_seed_user.py
uv run python scripts/dev_seed_demo.py
```

如果前端要走 JWT 联调，可以直接让 seed 脚本写入本地密码并输出 token pair：

```bash
uv run python scripts/dev_seed_user.py --password local-password --emit-token
uv run python scripts/dev_seed_demo.py --password local-password --emit-token
```

Auth token 闭环 smoke：

```bash
uv run python scripts/smoke_auth_token_loop.py
uv run python scripts/verify_local.py --smoke auth
uv run python scripts/smoke_auth_frontend_error_contract.py
uv run python scripts/verify_local.py --smoke auth-errors
```

### Auth Endpoints

#### POST `/auth/register`

注册用户并返回 access / refresh token。MVP 阶段用于正式 token 闭环，不承担复杂账号体系。

P1 注册只做 email + password，不接短信验证码、邮件验证、OTP、OAuth 或第三方账号服务；前端也不要为这些能力预留阻塞式流程。

Request:

```json
{
  "email": "alice@example.com",
  "password": "safe-password",
  "name": "Alice",
  "timezone": "Asia/Shanghai"
}
```

Response key fields:

```json
{
  "token_type": "bearer",
  "access_token": "jwt",
  "expires_in": 1800,
  "refresh_token": "opaque-token",
  "refresh_expires_in": 2592000,
  "user": {
    "id": "uuid",
    "email": "alice@example.com",
    "name": "Alice",
    "timezone": "Asia/Shanghai",
    "is_active": true
  }
}
```

#### POST `/auth/login`

使用 email / password 登录，返回同样的 token pair。

#### POST `/auth/refresh`

使用 refresh token 换取新的 access / refresh token。refresh token 会被轮换，旧 token 不能复用。

```json
{
  "refresh_token": "opaque-token"
}
```

#### POST `/auth/logout`

撤销 refresh token。接口是幂等语义，重复提交已撤销 token 仍返回成功。

#### GET `/auth/me`

JWT 模式下用当前 Bearer token 返回当前用户基础信息。

### Error Shape

所有显式业务错误统一返回：

```json
{
  "error": {
    "code": "INVALID_STATE",
    "message": "completed task cannot be postponed",
    "details": {}
  }
}
```

常见错误码：

| code | HTTP | 前端处理建议 |
| --- | --- | --- |
| `MISSING_USER_ID` | 400 | 开发态提示缺少 `X-User-Id` |
| `INVALID_USER_ID` | 400 | 用户上下文损坏，回到开发态入口 |
| `AUTH_REQUIRED` | 401 | 生产认证缺少 Bearer token，跳转登录 |
| `INVALID_AUTH_HEADER` | 401 | Authorization 格式错误，重新登录 |
| `INVALID_ACCESS_TOKEN` | 401 | token 无效，重新登录 |
| `ACCESS_TOKEN_EXPIRED` | 401 | token 过期，刷新 token 或重新登录 |
| `USER_NOT_FOUND` | 404 | 当前 user 不存在，重新 seed / 登录 |
| `USER_INACTIVE` | 403 | 用户已停用，退出当前会话 |
| `INSECURE_AUTH_CONFIGURATION` | 500 | 后端认证配置不安全，前端提示环境配置错误 |
| `AUTHENTICATION_FAILED` | 401 | 登录失败或 refresh token 无效，回到登录 |
| `CONFLICT` | 409 | 注册邮箱已存在 |
| `FORBIDDEN` | 403 | 用户或操作被禁止 |
| `NOT_FOUND` | 404 | 资源不存在或不属于当前用户 |
| `INVALID_STATE` | 400 | 按钮状态过期，刷新当前页面 |
| `VALIDATION_ERROR` | 400 | 业务字段不合法 |
| `REQUEST_VALIDATION_ERROR` | 422 | 请求结构不符合 schema |

### Data Format

- `id`：UUID string。
- `date`：`YYYY-MM-DD`。
- `datetime`：ISO datetime string。
- enum：全部使用 lowercase string，例如 `active`、`completed`、`high`。
- 列表接口当前使用 `limit` / `offset`，默认 `limit=50`。

---

## 3. 页面到接口映射

| 前端页面 / 场景 | 主要接口 | P1 状态 |
| --- | --- | --- |
| Global Capture | `POST /captures` | Ready |
| Inbox | `GET /inbox`, `PATCH /inbox/{id}`, `POST /inbox/{id}/confirm` | Ready |
| Today | `GET /today`, `GET /today/strategy`, `POST /today/replan`, `PATCH /today/items/{id}` | Ready, Strategy Detail P2 Ready |
| Task Detail | `GET /tasks/{id}`, `PATCH /tasks/{id}/priority`, `POST /tasks/{id}/breakdown`, dependencies / steps / complete / postpone | Ready, P2 priority / dependency ready |
| Focus | `POST /focus-sessions`, complete / interrupt / postpone | Ready |
| Reports | `GET /reports/daily`, `POST /reports/daily/generate`, `GET /reports/weekly`, `GET /reports/monthly` | Daily Ready, Weekly / Monthly P2 Ready |
| Me Overview | `GET /me/overview` | Ready |
| Insights | `GET /insights/detail` | P2 Ready |
| Goals | `GET /goals/home`, `GET /goals`, `POST /goals`, `GET /goals/{id}`, `GET /goals/{id}/detail`, `GET /goals/{id}/progress-timeline` | Backend Ready, P2 UI |
| AIJob Status | `GET /ai-jobs/{id}` | Backend Ready, mostly debug / future UI |

---

## 4. Capture

### POST `/captures`

用于全局 Capture 的文本输入。P1 只支持 text，voice / image 是 P3 以后。

Request:

```json
{
  "raw_text": "todo 写完今天的 PRD 梳理"
}
```

Response key fields:

```json
{
  "capture": {
    "id": "uuid",
    "input_type": "text",
    "raw_text": "todo 写完今天的 PRD 梳理",
    "source": "manual",
    "status": "parsed"
  },
  "parse_result": {
    "result_type": "task",
    "title": "todo 写完今天的 PRD 梳理",
    "estimated_duration_min": 25,
    "suggested_priority": 3,
    "confidence": "0.68"
  },
  "inbox_item": {
    "id": "uuid",
    "item_type": "task",
    "status": "pending"
  }
}
```

Frontend notes:

- Capture 成功后可以直接跳 Inbox，也可以用轻提示告诉用户“已放入待处理”。
- 不要把 `raw_model_output` 展示给用户，它是调试信息。

### GET `/captures/{capture_id}`

用于调试或详情回溯。P1 正常前端路径通常不需要主动进入 Capture Detail。

---

## 5. Inbox

### GET `/inbox`

Query:

```text
status=pending
include_all=false
limit=50
offset=0
```

Response:

```json
[
  {
    "id": "uuid",
    "item_type": "task",
    "title": "todo 写完今天的 PRD 梳理",
    "suggested_goal_id": null,
    "suggested_priority": 3,
    "suggested_deadline": null,
    "status": "pending",
    "result_entity_type": null,
    "result_entity_id": null
  }
]
```

### PATCH `/inbox/{item_id}`

用于用户确认前编辑 AI 解析结果。

Request:

```json
{
  "item_type": "task",
  "title": "写完今天的 PRD 梳理",
  "suggested_priority": 2,
  "suggested_deadline": "2026-05-16"
}
```

Allowed `item_type`:

```text
task | goal | idea | unknown
```

P1 只有 `task` / `goal` 可以 confirm。

### POST `/inbox/{item_id}/confirm`

确认后会生成 Task 或 Goal。

Response:

```json
{
  "inbox_item": {
    "id": "uuid",
    "status": "confirmed",
    "result_entity_type": "task",
    "result_entity_id": "uuid"
  },
  "result_entity_type": "task",
  "result_entity_id": "uuid",
  "today_impact": {
    "plan_date": "2026-05-17",
    "plan_exists": true,
    "replanned": true,
    "daily_plan_id": "uuid",
    "plan_version": 2,
    "daily_plan_item_id": "uuid",
    "task_in_today": true,
    "section": "recommended",
    "item_status": "planned",
    "reason": "replanned_existing_today_plan"
  }
}
```

Frontend notes:

- `result_entity_type=task` 后可以跳 Task Detail 或回 Today。
- `today_impact=null` 表示本次确认不影响 Today，例如确认 Goal。
- `today_impact.plan_exists=false` 表示当前还没有 active Today plan；前端不需要假设任务已进入今日编排，用户进入 Today 时由 `GET /today` 生成。
- `today_impact.replanned=true` 表示已有 Today plan 被系统刷新，新任务已纳入当前 plan version；前端可以刷新 Today 数据。
- 对已确认 item 重复调用 confirm 是幂等的：不会再次刷新 Today，只返回当前 `today_impact`。
- `result_entity_type=goal` 后 P1 可以轻提示创建成功；完整 Goal Detail 是 P2。
- 已确认 / 已丢弃 item 不可再编辑确认，前端应禁用操作。

### POST `/inbox/{item_id}/discard`

丢弃待处理输入。

---

## 6. Today

### GET `/today`

Query:

```text
plan_date=YYYY-MM-DD  // optional
```

Response shape:

```json
{
  "date": "2026-05-16",
  "greeting": "Ready when you are.",
  "daily_plan_id": "uuid",
  "plan_version": 1,
  "strategy": {
    "summary": "Use a steady order...",
    "mode": "normal",
    "primary_reason": "The sequence balances value, priority, and deadlines."
  },
  "progress": {
    "completed_count": 0,
    "total_count": 3,
    "focus_minutes": 0,
    "completion_rate": 0.0
  },
  "sections": {
    "pinned_tasks": [],
    "recommended_tasks": [],
    "low_priority_tasks": [],
    "rolled_over_tasks": []
  },
  "insights_preview": {
    "risk_alerts": [],
    "remaining_time_suggestion": {
      "key": "remaining_time",
      "title": "Remaining time",
      "message": "The remaining plan is light enough to keep a calm pace.",
      "signal": "positive",
      "task_id": null
    },
    "adjustment_suggestions": [],
    "source": "rule-today-insights-v1"
  },
  "quick_actions": {
    "can_replan": true,
    "can_capture": true,
    "can_view_report": true
  }
}
```

Task item fields:

```json
{
  "daily_plan_item_id": "uuid",
  "task_id": "uuid",
  "title": "Prepare the P1 execution loop demo",
  "goal_id": "uuid",
  "sort_order": 1,
  "section": "pinned",
  "recommendation_reason": "High-value task protected from being crowded out by lighter work.",
  "estimated_duration_min": 70,
  "item_status": "planned",
  "task_status": "active",
  "priority": 1,
  "value_level": "high",
  "deadline": "2026-05-16"
}
```

Frontend notes:

- Today 首页优先渲染 `strategy.summary`、`pinned_tasks`、`recommended_tasks` 和进度。
- `insights_preview` 是 P2 轻量预览，只展示风险提醒、剩余时间建议和最多几条调整建议。
- `recommendation_reason` 是解释文案，可在轻提示 / 展开区展示，不要让它抢占任务列表。
- P2 起 Today 后端排序会读取任务依赖和用户优先级修正信号；前端只消费服务端返回的分区和 `sort_order`，不自行重排。
- `rolled_over_tasks` 默认可以弱化或折叠。
- Strategy Detail 不在 Today 默认首屏展开，用户主动查看时再调用 `/today/strategy`。

### GET `/today/strategy`

Query:

```text
plan_date=YYYY-MM-DD  // optional
```

用于 P2 Strategy Detail。它解释当前 Today 策略，不重新排序、不修改 Task / Goal 状态；如果当天还没有 plan，会与 `GET /today` 一致 lazy create。

Response key fields:

```json
{
  "date": "2026-05-16",
  "daily_plan_id": "uuid",
  "plan_version": 1,
  "summary": "Use a steady order...",
  "mode": "normal",
  "primary_reason": "The sequence balances value, priority, and deadlines.",
  "revision": {
    "plan_revision_id": "uuid",
    "version": 1,
    "trigger": "initial",
    "reason": "Initial Today plan",
    "created_at": "2026-05-16T09:00:00Z"
  },
  "factors": {
    "task_count": 3,
    "high_value_task_count": 1,
    "pinned_count": 1,
    "recommended_count": 1,
    "low_priority_count": 1,
    "rolled_over_count": 0,
    "total_estimated_minutes": 95,
    "dependency_protected_count": 1,
    "user_adjusted_count": 1,
    "planner_agent_latency_ms": 12,
    "planner_agent_failure_type": null,
    "completed_count": 0,
    "focus_minutes": 0
  },
  "explanation": [
    "今天会平衡价值、截止时间和任务大小，不把 Today 变成复杂驾驶舱。"
  ],
  "task_rationales": [],
  "source": {
    "strategy_snapshot_id": "uuid",
    "ai_job_id": "uuid",
    "model_name": "planning-engine-v1",
    "prompt_version": "p2-planning-engine-v1",
    "generated_at": "2026-05-16T09:00:00Z"
  }
}
```

Frontend notes:

- 默认展示 `summary`、`primary_reason`、`explanation` 和少量 `factors`。
- `task_rationales` 复用 Today item 字段，可用于解释为什么某个任务被放在当前位置。
- `dependency_protected_count` 和 `user_adjusted_count` 只服务信任解释，不建议放入 Today 首屏。
- `planner_agent_latency_ms` 和 `planner_agent_failure_type` 只服务 Strategy Detail 深层解释或调试，不建议放入 Today 首屏。
- `source.ai_job_id` 指向本次 Daily Planner Agent shell 的 `AIJob` 记录；前端可在调试或 Strategy Detail 深层解释中查询，不建议在 Today 首屏展示。`AIJob.job_metadata.prompt_checksum` 可用于确认本次调用使用的 prompt 内容。
- 不要把完整 factors 做成复杂驾驶舱；它是信任解释，不是操作中心。

### POST `/today/replan`

Request:

```json
{
  "reason": "User requested Today replan"
}
```

返回新的 Today response。当前默认使用 Planning Engine v1 + mock Daily Planner Agent shell，不接真实 LLM。

### PATCH `/today/items/{item_id}`

Request:

```json
{
  "status": "postponed"
}
```

Allowed status:

```text
planned | completed | postponed | skipped
```

Frontend notes:

- Today 快速完成 / 延后可用该接口。
- 如果用户要进入专注态，优先进入 Task Detail，再 Start Focus。

---

## 7. Task Detail

### GET `/tasks/{task_id}`

Task Detail 是 Today / Goals 到 Focus 的承接层。P1 响应已经聚合了 Goal、AI info、Today context、Focus state 和可执行 actions。

Response key fields:

```json
{
  "id": "uuid",
  "title": "Prepare the P1 execution loop demo",
  "goal_id": "uuid",
  "estimated_duration_min": 70,
  "actual_duration_min": 0,
  "priority": 1,
  "value_level": "high",
  "deadline": "2026-05-16",
  "progress": "0.00",
  "status": "active",
  "source": "manual",
  "steps": [],
  "goal": {
    "id": "uuid",
    "title": "Ship Chronos P1 execution loop",
    "deadline": "2026-05-30",
    "value_level": "high"
  },
  "ai_info": {
    "recommended_duration_min": 70,
    "priority": 1,
    "value_level": "high",
    "execution_suggestion": "Start with one clear next action."
  },
  "today_context": {
    "daily_plan_id": "uuid",
    "daily_plan_item_id": "uuid",
    "plan_date": "2026-05-16",
    "plan_version": 1,
    "section": "pinned",
    "item_status": "planned",
    "sort_order": 1,
    "recommendation_reason": "High-value task protected..."
  },
  "dependency_info": {
    "task_id": "uuid",
    "prerequisites": [],
    "dependents": []
  },
  "focus_state": {
    "active_focus_session_id": null,
    "is_currently_focusing_this_task": false
  },
  "actions": {
    "can_start_focus": true,
    "can_complete": true,
    "can_postpone": true,
    "can_edit": true
  }
}
```

Frontend notes:

- 操作按钮以 `actions` 为准，不要只靠 `status` 自己推断。
- `today_context.daily_plan_item_id` 用于 Start Focus 时绑定 Today item。
- `dependency_info` 用于 P2 Dependency 区块，默认可折叠，不要让 Task Detail 变成信息仓库。
- `ai_info.execution_suggestion` 是轻量建议，不要做成大段解释。

### Task dependencies

用于 P2 Task Detail / Goal Detail 的 Dependency View。依赖方向统一为：

```text
prerequisite_task -> dependent_task
```

| Method | Path | 用途 |
| --- | --- | --- |
| `GET` | `/tasks/{task_id}/dependencies` | 获取当前任务的前置任务和后续任务 |
| `POST` | `/tasks/{task_id}/dependencies` | 为当前任务添加前置任务 |
| `DELETE` | `/tasks/{task_id}/dependencies/{prerequisite_task_id}` | 删除当前任务的一条前置依赖 |

POST request:

```json
{
  "prerequisite_task_id": "uuid",
  "reason": "Do this first"
}
```

Response key fields:

```json
{
  "task_id": "uuid",
  "prerequisites": [
    {
      "id": "uuid",
      "prerequisite_task": {
        "task_id": "uuid",
        "title": "Prepare context",
        "status": "active",
        "value_level": "high",
        "deadline": "2026-05-16"
      },
      "dependent_task": {
        "task_id": "uuid",
        "title": "Write final draft",
        "status": "active",
        "value_level": "high",
        "deadline": "2026-05-17"
      },
      "reason": "Do this first"
    }
  ],
  "dependents": []
}
```

Frontend notes:

- 自依赖、跨用户依赖会被拒绝。
- 形成环时返回 `400 INVALID_STATE`。
- Dependency View 默认展示少量边，复杂依赖图放到专门二级页，不压垮 Task Detail。

### POST `/tasks/{task_id}/breakdown`

P1 rule/mock 拆解任务步骤，不接真实 LLM。

Response:

```json
{
  "ai_job": {
    "id": "uuid",
    "job_type": "task_breakdown",
    "status": "succeeded_with_fallback",
    "result_entity_type": "task",
    "result_entity_id": "uuid",
    "error_message": null,
    "job_metadata": {
      "mode": "sync_rule_mock",
      "fallback_reason": "rule_mock_breakdown",
      "created_step_ids": ["uuid"]
    }
  },
  "created_steps": [
    {
      "id": "uuid",
      "task_id": "uuid",
      "title": "Clarify the finished state",
      "sort_order": 1,
      "is_completed": false,
      "completed_at": null
    }
  ]
}
```

Frontend notes:

- 如果 `created_steps=[]` 且 `fallback_reason=existing_steps_preserved`，说明已有步骤，前端展示已有步骤即可。
- 已完成 / 归档任务不可拆解，后端返回 `INVALID_STATE`。
- P1 不需要把 `AIJob` 暴露成用户页面，可作为调试和未来 loading 状态底座。

### Task actions

| Method | Path | 用途 |
| --- | --- | --- |
| `PATCH` | `/tasks/{task_id}` | 编辑任务基础字段 |
| `PATCH` | `/tasks/{task_id}/priority` | 调整任务优先级 / 价值等级 |
| `POST` | `/tasks/{task_id}/complete` | 直接完成任务 |
| `POST` | `/tasks/{task_id}/postpone` | 直接延后任务 |
| `GET` | `/tasks/{task_id}/dependencies` | 获取任务依赖 |
| `POST` | `/tasks/{task_id}/dependencies` | 添加任务依赖 |
| `DELETE` | `/tasks/{task_id}/dependencies/{prerequisite_task_id}` | 删除任务依赖 |
| `POST` | `/tasks/{task_id}/steps` | 手动添加步骤 |
| `POST` | `/tasks/{task_id}/steps/{step_id}/complete` | 完成步骤 |
| `GET` | `/tasks/{task_id}/events` | 调试 / 活动历史 |

### PATCH `/tasks/{task_id}/priority`

用于 P2 Task Detail 的“调整优先级”动作。它是一个窄接口，只记录用户对 AI 判断的修正信号，不替代完整任务编辑。

Request:

```json
{
  "priority": 1,
  "value_level": "high",
  "reason": "Protect this task today"
}
```

Rules:

- `priority` 和 `value_level` 至少提供一个。
- `priority` 范围是 `1-5`，数字越小越优先。
- 变更会写入 `TASK_PRIORITY_ADJUSTED` ActivityEvent。
- 不自动触发 Today replan；用户主动 replan 或生成新计划时，Today planner 会读取该修正信号。

Response key fields:

```json
{
  "task": {
    "id": "uuid",
    "title": "Prepare demo",
    "priority": 1,
    "value_level": "high"
  },
  "previous_priority": 5,
  "current_priority": 1,
  "previous_value_level": "low",
  "current_value_level": "high",
  "changed_fields": ["priority", "value_level"],
  "reason": "Protect this task today"
}
```

Frontend notes:

- Task Detail 里可以做成轻量 selector，不要做复杂策略面板。
- 调整后如果用户要刷新今日顺序，可以再调用 `/today/replan`，本接口本身不自动重排 Today。

---

## 8. Focus

### POST `/focus-sessions`

Request:

```json
{
  "task_id": "uuid",
  "daily_plan_item_id": "uuid",
  "planned_duration_min": 25
}
```

Response:

```json
{
  "id": "uuid",
  "task_id": "uuid",
  "daily_plan_id": "uuid",
  "daily_plan_item_id": "uuid",
  "started_at": "2026-05-16T10:00:00Z",
  "ended_at": null,
  "planned_duration_min": 25,
  "actual_duration_min": 0,
  "status": "active",
  "interruption_reason": null
}
```

Frontend notes:

- 同一用户同一时间只能有一个 active focus session。
- 如果存在 active session，Task Detail 的 `actions.can_start_focus=false`。
- `daily_plan_item_id` 推荐使用 Task Detail 的 `today_context.daily_plan_item_id` 传入。
- 如果前端未传 `daily_plan_item_id`，后端会尝试自动绑定当前 active Today 中的同一任务，保证 Focus 完成后 Today 进度和 Focus 时长不分叉。
- 如果任务不在当前 Today，Focus 仍可启动，但返回的 `daily_plan_item_id=null`，完成后只更新 Task / FocusSession / Report，不更新 Today item。

### Finish Focus

| Method | Path | Request | 状态结果 |
| --- | --- | --- | --- |
| `POST` | `/focus-sessions/{session_id}/complete` | `{ "actual_duration_min": 25 }` | `completed`，任务完成 |
| `POST` | `/focus-sessions/{session_id}/interrupt` | `{ "actual_duration_min": 10, "interruption_reason": "..." }` | `interrupted`，任务回到 active |
| `POST` | `/focus-sessions/{session_id}/postpone` | `{ "actual_duration_min": 10, "interruption_reason": "..." }` | `postponed`，任务延后 |

---

## 9. Daily Report

### GET `/reports/daily`

Query:

```text
report_date=YYYY-MM-DD  // optional
```

如果当日没有 report，会生成一个；如果已有 report 但完成数、延后数、中断数、Focus 时长或来源 plan version 已变化，会自动刷新同一条 Daily Report。

### POST `/reports/daily/generate`

强制重新生成当日 Daily Report。

Response key fields:

```json
{
  "id": "uuid",
  "report_date": "2026-05-16",
  "daily_plan_id": "uuid",
  "completed_task_count": 1,
  "postponed_task_count": 0,
  "interrupted_count": 0,
  "focus_minutes": 25,
  "completion_rate": 1.0,
  "ai_summary": "今天完成了主要执行动作。",
  "ai_suggestions": ["保持高价值任务优先。"],
  "generated_from_plan_version": 1
}
```

Frontend notes:

- P1 Daily Report 可以作为完成 Focus 后的轻量复盘入口。
- 前端可以直接 GET；后端会保证关键执行指标和最新 Focus / Today 数据对齐。`POST /generate` 仍可作为显式强制刷新入口。
- `ai_suggestions` 是短建议列表，不要做成复杂洞察页。

### GET `/reports/weekly`

Query:

```text
week_start=YYYY-MM-DD  // optional；后端会归一到该日期所在周的周一
```

用于 P2 Weekly Report。该接口不生成持久化 report，只基于已有执行数据做轻量聚合。

Response key fields:

```json
{
  "week_start": "2026-05-11",
  "week_end": "2026-05-17",
  "summary": {
    "total_planned_task_count": 8,
    "total_completed_task_count": 5,
    "total_postponed_task_count": 1,
    "total_interrupted_count": 1,
    "total_focus_minutes": 180,
    "average_completion_rate": 0.63,
    "high_value_completed_task_count": 2,
    "active_goal_count": 3,
    "at_risk_goal_count": 1,
    "overdue_task_count": 1
  },
  "daily_trends": [
    {
      "report_date": "2026-05-16",
      "planned_task_count": 3,
      "completed_task_count": 2,
      "postponed_task_count": 1,
      "interrupted_count": 0,
      "focus_minutes": 50,
      "completion_rate": 0.67,
      "high_value_completed_task_count": 1
    }
  ],
  "focus": {
    "total_minutes": 180,
    "average_minutes_per_active_day": 36,
    "best_focus_date": "2026-05-16",
    "best_focus_minutes": 50
  },
  "lagging_tasks": [
    {
      "id": "uuid",
      "title": "补齐课程项目提交",
      "goal_id": "uuid",
      "deadline": "2026-05-14",
      "days_overdue": 2,
      "value_level": "high",
      "priority": 1,
      "reason": "高价值任务已滞后 2 天，下次安排时需要优先保护。"
    }
  ],
  "ai_suggestions": ["先重新判断滞后任务是否仍重要，重要的保留，不重要的后移或归档。"]
}
```

Frontend notes:

- Weekly Report 是 P2 趋势反馈入口，不要替代 Today 的执行决策。
- 默认展示 summary、daily trends、focus summary 和最多 5 个 lagging tasks。
- `ai_suggestions` 仍是规则建议，不代表真实 LLM 洞察。
- Monthly Report 已提供独立 `/reports/monthly` 聚合接口。

---

## 10. Me

### GET `/me/overview`

Query:

```text
today=YYYY-MM-DD  // optional
```

Response:

```json
{
  "profile": {
    "user_id": "uuid",
    "name": "Chronos Demo",
    "timezone": "Asia/Shanghai",
    "current_streak_days": 1
  },
  "today": {
    "date": "2026-05-16",
    "completed_task_count": 1,
    "planned_task_count": 3,
    "completion_rate": 0.33,
    "focus_minutes": 25
  },
  "week": {
    "week_start": "2026-05-11",
    "week_end": "2026-05-17",
    "focus_minutes": 25
  },
  "goals": {
    "active_goal_count": 1,
    "completed_goal_count": 0
  },
  "tasks": {
    "active_task_count": 2,
    "postponed_task_count": 1,
    "completed_task_count": 1
  },
  "reports": {
    "daily_report_available": true,
    "daily_report_id": "uuid"
  },
  "insights": {
    "highlights": [
      {
        "key": "strong_today",
        "title": "Strong execution today",
        "message": "Most planned work is complete. A short report can help close the loop.",
        "signal": "positive"
      }
    ],
    "suggested_next_view": "insights_detail",
    "detail_available": true
  },
  "settings": {
    "notification_enabled": true,
    "focus_mode_default_minutes": 25,
    "reminder_execution_enabled": true,
    "reminder_deadline_enabled": true
  }
}
```

Frontend notes:

- P1 Me 是数据收敛页，不是完整洞察中心。
- `insights` 是 P2 轻量概览，默认最多展示少量 highlights。
- Insights 详情入口已可调用 `/insights/detail`；Energy、Social 入口仍保留占位。

### GET `/insights/detail`

Query:

```text
anchor_date=YYYY-MM-DD  // optional；后端按该日期所在周聚合
```

用于 P2 Insight Detail。它是 Me -> Insights 的二级页，只读聚合，不修改任务或目标。

Response key fields:

```json
{
  "anchor_date": "2026-05-16",
  "period_start": "2026-05-11",
  "period_end": "2026-05-17",
  "overview": {
    "average_completion_rate": 0.63,
    "total_completed_task_count": 5,
    "high_value_completed_task_count": 2,
    "total_focus_minutes": 180,
    "overdue_task_count": 1,
    "at_risk_goal_count": 1
  },
  "behavior_patterns": [
    {
      "key": "high_value_progress",
      "title": "高价值任务有推进",
      "signal": "positive",
      "evidence": "本周完成了 2 个高价值任务。",
      "suggestion": "下周继续把高价值任务放在 Today 的前段。"
    }
  ],
  "efficiency_windows": [
    {
      "label": "morning",
      "start_hour": 5,
      "end_hour": 12,
      "focus_minutes": 90,
      "completed_focus_count": 2,
      "signal": "strong"
    }
  ],
  "recommendations": [
    {
      "category": "schedule",
      "title": "把难任务放到优势时段",
      "suggestion": "下周优先在上午开始一个高价值任务。",
      "rationale": "这是本周 Focus 时长最集中的时段。"
    }
  ],
  "strategy_notes": ["下周 Today 编排需要继续保护有风险的 Goal，避免被轻任务挤掉。"],
  "source": {
    "generated_by": "rule-insight-v1",
    "period_days": 7,
    "data_points": 5
  }
}
```

Frontend notes:

- 默认展示 `overview`、1-3 条 `behavior_patterns`、1-3 条 `recommendations`。
- `efficiency_windows` 是轻量时段判断，不是健康 / 精力模型。
- `strategy_notes` 可作为 Today 调度解释的补充，不要替代 Today 的行动序列。
- 该接口当前是规则洞察，不代表真实 LLM 分析。

---

### GET `/reports/monthly`

Query:

```text
month=YYYY-MM-DD  // optional；后端会归一到该日期所在月份
```

用于 P2 Monthly Report。该接口不生成持久化 report，只基于已有执行数据做月度轻量聚合。

Response key fields:

```json
{
  "month_start": "2026-05-01",
  "month_end": "2026-05-31",
  "summary": {
    "total_planned_task_count": 22,
    "total_completed_task_count": 14,
    "high_value_completed_task_count": 4,
    "total_focus_minutes": 620,
    "average_completion_rate": 0.64,
    "active_goal_count": 3,
    "at_risk_goal_count": 1,
    "overdue_task_count": 1
  },
  "weekly_trends": [],
  "daily_trends": [],
  "ai_suggestions": ["下月开始前先清理滞后任务，避免它们持续挤占 Today。"]
}
```

Frontend notes:

- Monthly Report 是长期趋势入口，不要替代 Today 的每日执行顺序。
- 默认展示 summary 和 weekly trends；daily trends 可用于图表，不一定全量铺开。
- 该接口当前是规则聚合，不代表真实 LLM 月度分析。

## 11. Goals

Goals 是 P2 一级 Tab，但 P1 后端已经提供轻量 Goal API，主要用于 Task 归属和后续 Goals 页面。

| Method | Path | 用途 |
| --- | --- | --- |
| `POST` | `/goals` | 创建目标 |
| `GET` | `/goals` | 轻量目标列表 / selector |
| `GET` | `/goals/home` | Goals 首页聚合 |
| `GET` | `/goals/{goal_id}` | 目标详情基础信息 |
| `GET` | `/goals/{goal_id}/detail` | Goal Detail 聚合 |
| `GET` | `/goals/{goal_id}/progress-timeline` | Goal Progress Timeline |
| `PATCH` | `/goals/{goal_id}` | 编辑目标基础字段 |

Goal fields:

```json
{
  "id": "uuid",
  "title": "Ship Chronos P1 execution loop",
  "description": "Demo goal",
  "deadline": "2026-05-30",
  "value_level": "high",
  "status": "active"
}
```

P2 Goals 已提供：

- Goals Home Summary。
- Goal List progress / deadline / risk / task count。
- Goals filters: `all` / `active` / `due_soon` / `completed` / `high_value`。
- Goal Overview。
- Goal Progress。
- Goal Progress Timeline。
- Goal Task List。
- 规则版 AI Suggestion。
- Dependency Map 节点顺序和真实依赖边。

尚未实现：

- 深度 Goal 洞察。

### GET `/goals/{goal_id}/progress-timeline`

用于 P2 Goal Detail 的 Goal Progress 区块。该接口只读，基于 Goal、关联 Task 和 ActivityEvent 生成轻量时间线。

Query:

```text
limit=30  // optional, 1-100
```

Response key fields:

```json
{
  "goal_id": "uuid",
  "generated_at": "2026-05-16T09:00:00Z",
  "summary": {
    "goal_id": "uuid",
    "goal_status": "active",
    "deadline": "2026-05-30",
    "total_task_count": 4,
    "completed_task_count": 2,
    "completion_rate": 0.5,
    "risk_level": "on_track",
    "risk_reason": "Goal has a clear next task and no urgent deadline risk."
  },
  "milestones": [
    {
      "milestone_type": "task_completed",
      "event_type": "TASK_COMPLETED",
      "title": "Task completed",
      "description": "A linked task was completed. Task: Prepare demo.",
      "signal": "positive",
      "task_id": "uuid",
      "occurred_at": "2026-05-16T09:00:00Z",
      "milestone_date": "2026-05-16"
    }
  ],
  "note": "Timeline is derived from goal and task activity events; it does not change Today ordering."
}
```

Frontend notes:

- 默认展示 summary 和最多 5-8 个 milestones。
- `signal` 可用于轻量视觉区分：`positive` / `neutral` / `risk`。
- Timeline 不做甘特图，不替代 Dependency Map，也不触发 Today 重排。

---

## 12. AIJob

### GET `/ai-jobs/{job_id}`

用于查询 AI / fallback job 状态。P1 主要给 Task Breakdown 使用。

Response key fields:

```json
{
  "id": "uuid",
  "job_type": "task_breakdown",
  "status": "succeeded_with_fallback",
  "input_entity_type": "task",
  "input_entity_id": "uuid",
  "result_entity_type": "task",
  "result_entity_id": "uuid",
  "provider": "rule",
  "model": "task-breakdown-rule",
  "prompt_version": "p1-rule-v1",
  "retry_count": 0,
  "job_metadata": {}
}
```

Frontend notes:

- P1 不建议做 AIJob 列表页。
- 未来真实 LLM / async worker 接入后，前端可以用它支持 loading、失败、重试提示。

---

## 13. 推荐前端调用流程

### 输入闭环

```text
POST /captures
-> show parsed inbox item
-> optional PATCH /inbox/{id}
-> POST /inbox/{id}/confirm
-> if task: GET /tasks/{task_id}
-> if goal: show created state / later enter Goals
```

### 今日执行闭环

```text
GET /today
-> user taps task
-> GET /tasks/{task_id}
-> optional POST /tasks/{task_id}/breakdown
-> POST /focus-sessions
-> POST /focus-sessions/{id}/complete | interrupt | postpone
-> GET /today
-> GET /reports/daily
```

### 复盘闭环

```text
GET /reports/daily
GET /me/overview
```

---

## 14. P1 前端不要依赖的内容

以下是后续阶段能力，前端 P1 可以保留入口或占位，但不要假设后端已完成：

- Voice / Image capture。
- Calendar / Email / Health 数据接入。
- Energy dashboard。
- Social / Groups / Friends。
- Notification center。
- AIJob list / cancel / retry。
- 真实 LLM planning / task breakdown。

---

## 15. 本地验收命令

```bash
uv run alembic upgrade head
uv run python scripts/dev_seed_demo.py
uv run python scripts/smoke_p1_execution_loop.py
uv run python scripts/smoke_p1_mainline_contract.py
uv run python scripts/verify_local.py --smoke p1-mainline
uv run python -m unittest discover -s tests
```

本地 API 文档：

```text
http://localhost:8000/docs
```
