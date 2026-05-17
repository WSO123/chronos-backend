# Chronos P1 Bearer API Walkthrough

> 版本：v1  
> 日期：2026-05-17  
> 适用范围：前端本地联调 / Postman-like curl contract

---

## 1. 目的

这份 walkthrough 用 Bearer token 跑通 P1 主闭环：

```text
Seed Demo User -> Auth Me -> Today -> Task Detail -> Focus -> Daily Report -> Me Overview
```

它不是新的产品需求，而是前端联调手册。目标是让前端可以确认：真实 JWT 会话下，Chronos 的 Today 决策中心、Task Detail 承接层、Focus 执行页和 Report 反馈层能串起来。

---

## 2. 前置条件

启动基础设施并迁移数据库：

```bash
docker compose up -d
uv run alembic upgrade head
```

启动 API 时使用 JWT 模式。可以写入 `.env` 后重启服务，也可以临时带环境变量启动：

```bash
AUTH_MODE=jwt ENVIRONMENT=development uv run uvicorn main:app --reload
```

本地开发环境可以使用默认 `SECRET_KEY`；生产 / 准生产环境不能使用默认值。

---

## 3. 准备 Demo 数据和 Token

创建 demo 用户、P1 demo 数据，并输出 token pair：

```bash
uv run python scripts/dev_seed_demo.py --password local-password --emit-token
```

从输出 JSON 里复制：

- `auth.access_token`
- `auth.refresh_token`
- `high_value_task_id`，可用于核对 Today 第一条高价值任务

设置本地变量：

```bash
export BASE_URL="http://localhost:8000/api/v1"
export ACCESS_TOKEN="<copy auth.access_token>"
export REFRESH_TOKEN="<copy auth.refresh_token>"
```

后续 curl 示例使用 `jq` 阅读和提取字段。

---

## 4. 自动 Smoke

如果只是想快速确认 Bearer token 版 P1 主链路是否可用：

```bash
uv run python scripts/smoke_p1_bearer_execution_loop.py
uv run python scripts/verify_local.py --smoke p1-bearer
```

这条 smoke 会自动完成：

```text
seed demo data
-> issue token
-> GET /auth/me
-> GET /today
-> GET /tasks/{task_id}
-> POST /focus-sessions
-> POST /focus-sessions/{id}/complete
-> POST /reports/daily/generate
-> GET /me/overview
```

---

## 5. 手动 Curl Walkthrough

### 5.1 校验当前会话

```bash
curl -sS "$BASE_URL/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq
```

期望：

- `email` 是 seed demo 用户。
- `is_active` 为 `true`。

如果返回 `MISSING_USER_ID`，说明服务仍在 `AUTH_MODE=dev_header`；需要切到 `AUTH_MODE=jwt` 后重启 API。

### 5.2 读取 Today

```bash
curl -sS "$BASE_URL/today" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | tee /tmp/chronos_today.json \
  | jq '{
      date,
      daily_plan_id,
      plan_version,
      strategy,
      progress,
      first_task: ([.sections.pinned_tasks[], .sections.recommended_tasks[], .sections.low_priority_tasks[], .sections.rolled_over_tasks[]] | .[0])
    }'
```

提取第一个可执行任务：

```bash
export TASK_ID="$(
  jq -r '[.sections.pinned_tasks[], .sections.recommended_tasks[], .sections.low_priority_tasks[], .sections.rolled_over_tasks[]] | .[0].task_id' /tmp/chronos_today.json
)"
export DAILY_PLAN_ITEM_ID="$(
  jq -r '[.sections.pinned_tasks[], .sections.recommended_tasks[], .sections.low_priority_tasks[], .sections.rolled_over_tasks[]] | .[0].daily_plan_item_id' /tmp/chronos_today.json
)"
```

前端页面对应：

- Today Header：`date`、`greeting`
- AI Strategy Card：`strategy`
- Task List：`sections`
- Progress：`progress`
- Today Insights Preview：`insights_preview`

### 5.3 进入 Task Detail

```bash
curl -sS "$BASE_URL/tasks/$TASK_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | tee /tmp/chronos_task_detail.json \
  | jq '{
      id,
      title,
      status,
      ai_info,
      today_context,
      focus_state,
      actions,
      steps
    }'
```

前端页面对应：

- Basic Info：`title`、`goal`、`deadline`、`source_context`
- AI Info：`ai_info`
- Progress：`progress_info`
- Subtasks / Steps：`steps`
- Actions：`actions`

Task Detail 只展示承接执行所需信息，不要把 `score_breakdown` 或调试型 AIJob 细节堆到页面里。

### 5.4 Start Focus

```bash
jq -n \
  --arg task_id "$TASK_ID" \
  --arg daily_plan_item_id "$DAILY_PLAN_ITEM_ID" \
  '{
    task_id: $task_id,
    daily_plan_item_id: $daily_plan_item_id,
    planned_duration_min: 25
  }' \
  | curl -sS -X POST "$BASE_URL/focus-sessions" \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      --data @- \
  | tee /tmp/chronos_focus.json \
  | jq
```

提取 Focus Session：

```bash
export FOCUS_SESSION_ID="$(jq -r '.id' /tmp/chronos_focus.json)"
```

前端页面对应：

- Current Task：来自 Task Detail
- Timer：`planned_duration_min`
- Actions：后续 complete / interrupt / postpone

### 5.5 Complete Focus

```bash
curl -sS -X POST "$BASE_URL/focus-sessions/$FOCUS_SESSION_ID/complete" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"actual_duration_min": 12}' \
  | tee /tmp/chronos_focus_complete.json \
  | jq
```

期望：

- `status` 为 `completed`。
- `actual_duration_min` 为 `12`。

### 5.6 回到 Today 查看进度

```bash
curl -sS "$BASE_URL/today" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | tee /tmp/chronos_today_after_focus.json \
  | jq '{
      progress,
      completed_task: ([.sections.pinned_tasks[], .sections.recommended_tasks[], .sections.low_priority_tasks[], .sections.rolled_over_tasks[]] | map(select(.task_id == env.TASK_ID)) | .[0])
    }'
```

期望：

- `progress.completed_count >= 1`
- 当前任务的 `item_status` 为 `completed`

### 5.7 生成 Daily Report

```bash
curl -sS -X POST "$BASE_URL/reports/daily/generate" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | tee /tmp/chronos_daily_report.json \
  | jq '{
      report_date,
      completed_task_count,
      focus_minutes,
      completion_rate,
      ai_summary,
      ai_suggestions
    }'
```

期望：

- `completed_task_count >= 1`
- `focus_minutes >= 12`
- `ai_summary` 和 `ai_suggestions` 可以直接服务 Daily Report 页面，但前端仍应保持复盘轻量。

### 5.8 查看 Me Overview

```bash
curl -sS "$BASE_URL/me/overview" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | jq '{
      profile,
      today,
      week,
      goals,
      reports,
      settings
    }'
```

前端页面对应：

- Profile：`profile`
- Data Overview：`today`、`week`、`goals`
- Reports Entry：`reports`
- Settings Entry：`settings`

---

## 6. Refresh / Logout

刷新 token：

```bash
jq -n --arg refresh_token "$REFRESH_TOKEN" '{refresh_token: $refresh_token}' \
  | curl -sS -X POST "$BASE_URL/auth/refresh" \
      -H "Content-Type: application/json" \
      --data @- \
  | tee /tmp/chronos_refresh.json \
  | jq
```

refresh token 会轮换。前端拿到新 token pair 后，应替换本地保存的 access / refresh token，旧 refresh token 不能继续使用。

退出登录：

```bash
export NEW_REFRESH_TOKEN="$(jq -r '.refresh_token' /tmp/chronos_refresh.json)"

jq -n --arg refresh_token "$NEW_REFRESH_TOKEN" '{refresh_token: $refresh_token}' \
  | curl -sS -X POST "$BASE_URL/auth/logout" \
      -H "Content-Type: application/json" \
      --data @- \
  | jq
```

---

## 7. 常见错误

| 错误 | 常见原因 | 处理 |
| --- | --- | --- |
| `MISSING_USER_ID` | API 仍是 `AUTH_MODE=dev_header` | 切到 `AUTH_MODE=jwt` 并重启 |
| `AUTH_REQUIRED` | 没传 Bearer token | 检查 `Authorization` header |
| `INVALID_ACCESS_TOKEN` | access token 无效 | 重新 login 或刷新 token |
| `ACCESS_TOKEN_EXPIRED` | access token 过期 | 调 `/auth/refresh` |
| `AUTHENTICATION_FAILED` | refresh token 无效、过期或已轮换 | 回到 login |
| `NOT_FOUND` | 资源不属于当前用户或 ID 已过期 | 重新 GET Today / Task Detail |
| `INVALID_STATE` | 任务已完成、已有 active focus 等状态冲突 | 刷新当前页面状态 |

---

## 8. 联调边界

- Bearer token 是正式会话路径；`X-User-Id` 只保留给本地开发态。
- Today 只展示轻量决策结果，不展示完整算法内部状态。
- Task Detail 是执行承接层，不做信息仓库。
- Focus 页只保留当前任务、计时、步骤和完成 / 中断 / 延后动作。
- Report 和 Me 是反馈层，不应抢走用户继续行动的主线。
