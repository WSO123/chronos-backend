# Chronos P3 Frontend API Contract

日期：2026-05-17
状态：P3 foundation contract

## 1. 目的

本文档沉淀 P3 自然生长模块的第一批后端接口合同。

当前 P3 已完成数据源连接状态底座和外部来源导入入口，用来承接：

```text
Me -> Settings -> 数据接入
Calendar / Email / Health -> Capture / Inbox -> Today
Health -> Energy Dashboard -> Today 调度辅助
```

P3 原则仍然是：外部能力只作为输入和上下文，不直接绕过用户确认，不让 Today 变成复杂驾驶舱。

## 2. P3 Ready Map

| 场景 | 接口 | 状态 |
| --- | --- | --- |
| Data Source Catalog | `GET /api/v1/data-sources` | Ready |
| Connect Data Source Placeholder | `PUT /api/v1/data-sources/{source_type}/{provider}` | Ready |
| Update Data Source Status | `PATCH /api/v1/data-sources/{connection_id}` | Ready |
| Data Source Sync Runs | `GET /api/v1/data-sources/{connection_id}/sync-runs` | Ready |
| Disconnect Data Source | `POST /api/v1/data-sources/{connection_id}/disconnect` | Ready |
| External Capture Import | `POST /api/v1/captures/external-imports` | Ready |
| Task Detail Source Context | `GET /api/v1/tasks/{task_id}` | Ready |
| Calendar Sync Worker Placeholder | `data_source.sync_connection` | Ready |
| Email Sync Worker Placeholder | `data_source.sync_connection` | Ready |
| Calendar / Email Fake Provider Adapter | internal provider registry | Ready |
| Energy Daily Metric Upsert | `PUT /api/v1/energy/daily-metrics` | Ready |
| Energy Dashboard | `GET /api/v1/energy/dashboard` | Ready |
| Health Energy Sync Worker | `health.sync_energy_connection` | Ready |
| Health Fake Provider Adapter | internal health provider registry | Ready |
| Today Strategy Energy Explanation | `GET /api/v1/today/strategy` -> `energy` | Ready |
| Notification Center | - | Not Started |

## 3. Data Sources

### GET `/api/v1/data-sources`

用于 Me / Settings 的“数据接入”页面。

Response key fields:

```json
{
  "sources": [
    {
      "source_type": "calendar",
      "display_name": "Calendar",
      "supported_providers": ["google_calendar", "outlook_calendar", "apple_calendar"],
      "default_scopes": ["calendar.read"],
      "capabilities": ["task_import", "rolling_plan_context", "reminder_context"],
      "status": "disconnected",
      "connection": null
    }
  ],
  "connected_count": 0
}
```

Frontend notes:

- 默认展示 `calendar`、`email`、`health` 三类入口。
- `connection=null` 表示尚未连接。
- 不要假设已完成真实 OAuth；当前是连接状态底座。

### PUT `/api/v1/data-sources/{source_type}/{provider}`

用于创建或重新连接一个数据源。

Supported:

| source_type | providers |
| --- | --- |
| `calendar` | `google_calendar`, `outlook_calendar`, `apple_calendar` |
| `email` | `gmail`, `outlook_email` |
| `health` | `apple_health`, `google_fit` |

Request:

```json
{
  "external_account_label": "alice@example.com",
  "scopes": ["calendar.read"],
  "sync_enabled": true,
  "connection_metadata": {
    "origin": "settings"
  }
}
```

Rules:

- `scopes` 不传时使用后端默认 scopes。
- 当前不保存 OAuth token。
- 连接或重连会写入 `DATA_SOURCE_CONNECTED` / `DATA_SOURCE_RECONNECTED`。

### PATCH `/api/v1/data-sources/{connection_id}`

用于更新连接状态或同步元数据。

Request:

```json
{
  "status": "paused",
  "sync_enabled": false,
  "last_sync_at": "2026-05-16T09:00:00Z",
  "sync_cursor": "opaque-cursor"
}
```

Rules:

- 至少传一个字段。
- 可用于 worker 写入 `last_sync_at` 和 `sync_cursor`。
- 更新会写入 `DATA_SOURCE_UPDATED`。

### GET `/api/v1/data-sources/{connection_id}/sync-runs`

用于 Me / Settings 或开发调试查看最近同步记录，不会触发同步。

Response key fields:

```json
[
  {
    "id": "uuid",
    "data_source_connection_id": "uuid",
    "source_type": "email",
    "provider": "gmail",
    "status": "succeeded",
    "trigger": "worker",
    "attempt": 1,
    "max_attempts": 3,
    "retryable": false,
    "next_retry_at": null,
    "skip_reason": null,
    "error_message": null,
    "processed_count": 1,
    "imported_count": 1,
    "reused_count": 0,
    "fetched_from_provider": true,
    "provider_mode": "fake",
    "sync_cursor_before": null,
    "sync_cursor_after": "fake-cursor-2",
    "started_at": "2026-05-17T09:00:00Z",
    "finished_at": "2026-05-17T09:00:01Z",
    "duration_ms": 120,
    "run_metadata": {
      "import_record_ids": ["uuid"]
    }
  }
]
```

Rules:

- 只返回当前用户自己的连接同步记录。
- 默认用于展示最近同步状态和失败原因。
- `status=failed` 时可读取 `retryable` / `next_retry_at`，但当前不会自动重试。
- 不返回外部平台 token 或完整第三方响应。

### POST `/api/v1/data-sources/{connection_id}/disconnect`

用于断开连接。

Response key fields:

```json
{
  "id": "uuid",
  "source_type": "calendar",
  "provider": "google_calendar",
  "status": "disconnected",
  "sync_enabled": false,
  "revoked_at": "2026-05-16T09:00:00Z"
}
```

Rules:

- 断开后保留连接记录，用于审计和后续重连。
- 断开会写入 `DATA_SOURCE_DISCONNECTED`。

## 4. External Capture Imports

### POST `/api/v1/captures/external-imports`

用于 Calendar / Email worker 将外部条目规范导入 Capture / Inbox。

Request:

```json
{
  "data_source_connection_id": "uuid",
  "external_item_id": "calendar-event-123",
  "external_item_type": "calendar_event",
  "title": "完成项目复盘",
  "body": "整理会议结论",
  "occurred_at": "2026-05-17T09:00:00Z",
  "external_payload": {
    "html_link": "https://calendar.example/event"
  }
}
```

Response key fields:

```json
{
  "created": true,
  "import_record": {
    "id": "uuid",
    "source": "calendar",
    "provider": "google_calendar",
    "external_item_id": "calendar-event-123",
    "capture_input_id": "uuid",
    "inbox_item_id": "uuid"
  },
  "capture": {
    "input_type": "external",
    "source": "calendar",
    "status": "parsed"
  },
  "inbox_item": {
    "status": "pending",
    "title": "完成项目复盘"
  }
}
```

Rules:

- 仅支持 `calendar` / `email` 类型的数据源连接。
- 数据源必须是 `connected` 且 `sync_enabled=true`。
- 同一个 `user_id + source + provider + external_item_id` 重复导入时不会重复创建 Capture / Inbox，返回 `created=false`。
- 导入会写入 `EXTERNAL_CAPTURE_IMPORTED`。
- 用户确认 Inbox 后，生成的 Task 会保留来源：`calendar` 或 `email`。
- Health 数据不走该接口，后续进入 Energy / Health 专用模型。

Frontend notes:

- 该接口主要给后端 worker / 内部工具使用，不是普通用户手动输入入口。
- 外部来源内容必须先进入 Inbox，由用户确认后才生成 Task / Goal。

## 5. Task Detail Source Context

### GET `/api/v1/tasks/{task_id}`

当任务来自 Calendar / Email 外部导入并经过 Inbox 确认后，Task Detail 会返回轻量来源上下文：

```json
{
  "id": "task-uuid",
  "source": "calendar",
  "source_context": {
    "source": "calendar",
    "capture_source": "calendar",
    "provider": "google_calendar",
    "external_item_id": "calendar-event-123",
    "external_item_type": "calendar_event",
    "external_title": "完成项目复盘",
    "external_body_preview": "整理会议结论",
    "occurred_at": "2026-05-17T09:00:00Z",
    "imported_at": "2026-05-17T09:05:00Z",
    "capture_input_id": "uuid",
    "inbox_item_id": "uuid",
    "data_source_connection_id": "uuid"
  }
}
```

Rules:

- `source_context=null` 表示手动创建、普通 Capture 创建，或暂时没有可追溯外部导入记录。
- 只在 Task Detail 展示轻量来源解释，用于帮助用户理解“这个任务从哪里来”。
- 不返回 `external_payload`、`normalized_text`、完整邮件正文或完整日历原始对象，避免 Task Detail 变成信息仓库。
- 需要查看完整来源对象时，后续应通过独立来源详情接口承接，而不是继续扩展 Task Detail。

Frontend notes:

- 可在 Task Detail 的 Basic Info / Related Context 区域展示为一行来源卡。
- 文案应克制，例如：`来自 Google Calendar · calendar_event · 完成项目复盘`。
- 不要在 Today 任务列表中展开这些字段。

## 6. Connector Worker Placeholder

当前已具备 Calendar / Email 的内部 worker 占位同步能力和 fake provider adapter，但仍不接真实第三方 API。

Celery tasks:

```text
data_source.sync_connection(connection_id, items=null, sync_cursor=null)
data_source.sync_ready_connections(limit=50)
```

`data_source.sync_connection` 的输入规则：

- `items=null`：通过 provider adapter 拉取条目；当前使用 fake provider adapter。
- `items=[]`：显式传入空同步结果，不拉取 provider。
- `items=[...]`：使用调用方传入的规范化 item。

规范化 item 使用 External Capture Import 的标准 item 形状：

```json
{
  "external_item_id": "calendar-event-123",
  "external_item_type": "calendar_event",
  "title": "完成项目复盘",
  "body": "整理会议结论",
  "occurred_at": "2026-05-17T09:00:00Z",
  "external_payload": {
    "html_link": "https://calendar.example/event"
  }
}
```

Worker rules:

- 只处理 `calendar` / `email` 连接。
- 只有 `status=connected` 且 `sync_enabled=true` 的连接会同步。
- 当前 fake provider adapter 从 `DataSourceConnection.connection_metadata.fake_items` 读取测试条目。
- fake provider 可读取 `connection_metadata.fake_next_cursor` 作为下一次 cursor。
- 同步成功后更新 `last_sync_at`，传入 `sync_cursor` 时更新连接 cursor。
- 如果通过 provider adapter 获取到 `next_cursor` 且调用方未显式传入 `sync_cursor`，后端会使用 provider 返回的 cursor。
- 每个外部 item 仍通过 `ExternalCaptureImport -> Capture -> Inbox`，不会直接生成 Task。
- 重复 item 依赖 `user_id + source + provider + external_item_id` 幂等复用。
- Worker 写入 `DataSourceSyncRun`，并记录 `DATA_SOURCE_SYNCED` / `DATA_SOURCE_SYNC_SKIPPED` / `DATA_SOURCE_SYNC_FAILED`。
- 批量同步中单个连接失败时，worker 会记录 failed run 并继续处理后续连接；返回 `partial_failed` 和 `failed_connection_count` 供后台观测。

Fake provider metadata example:

```json
{
  "connection_metadata": {
    "fake_items": [
      {
        "external_item_id": "fake-calendar-1",
        "title": "完成项目复盘",
        "body": "整理会议结论"
      }
    ],
    "fake_next_cursor": "fake-cursor-2"
  }
}
```

Frontend notes:

- 这不是前端直接调用的接口。
- Me / Settings 仍只依赖 Data Source 状态接口展示连接和最近同步时间。
- 当前 worker 和 fake provider 的价值是打通后端承接层；真实 OAuth、真实 provider 拉取、定时调度仍在后续迭代。

## 7. Energy / Health Dashboard

Health 数据不走 Capture / Inbox，不会生成 Task。当前先支持日级聚合数据和只读 Dashboard，服务 Me -> Energy Dashboard，并为后续 Today 的精力解释预留输入。

### PUT `/api/v1/energy/daily-metrics`

用于写入或更新某一天的睡眠、压力、精力聚合数据。当前可用于手动 check-in、测试导入或后续 Health provider worker。

Request:

```json
{
  "metric_date": "2026-05-17",
  "source": "manual",
  "data_source_connection_id": null,
  "sleep_minutes": 450,
  "sleep_quality_score": 82,
  "stress_score": 30,
  "energy_score": null,
  "note": "slept well",
  "metric_metadata": {
    "entry": "manual_checkin"
  }
}
```

Rules:

- `source` 当前支持 `manual` / `health_import` / `estimated`。
- 至少需要一个指标：`sleep_minutes` / `sleep_quality_score` / `stress_score` / `energy_score`。
- 如果没有传 `energy_score`，后端用轻量规则从睡眠和压力推导一个 `energy_score`。
- `data_source_connection_id` 如存在，必须属于当前用户且是 `health` 数据源。
- 同一用户同一天只有一条聚合 metric，重复提交会更新。
- 不保存原始 HealthKit / Google Fit payload，也不保存 token。

### GET `/api/v1/energy/dashboard`

Query:

```text
end_date=2026-05-17
days=7
```

Response key fields:

```json
{
  "start_date": "2026-05-11",
  "end_date": "2026-05-17",
  "summary": {
    "date": "2026-05-17",
    "energy_score": 83,
    "energy_level": "high",
    "sleep_minutes": 450,
    "sleep_quality_score": 82,
    "stress_score": 30,
    "status_message": "Energy looks strong. This is a good day for deeper high-value work."
  },
  "trends": [
    {
      "date": "2026-05-17",
      "sleep_minutes": 450,
      "sleep_quality_score": 82,
      "stress_score": 30,
      "energy_score": 83,
      "energy_level": "high",
      "has_data": true
    }
  ],
  "task_match": {
    "recommended_mode": "deep_work",
    "reason": "Energy is high enough for focused high-value tasks."
  },
  "suggestions": [
    {
      "key": "protect_deep_work",
      "title": "Protect deeper work",
      "message": "This is a good window to move one high-value task forward.",
      "signal": "positive"
    }
  ]
}
```

Frontend notes:

- Energy Dashboard 可以展示睡眠趋势、压力趋势、精力曲线和任务类型建议。
- Today 仍不直接依赖该接口改变排序；后续如接入 Today，只能作为解释性输入和可回滚的策略因子。
- 文案应保持克制，避免用健康数据制造压力。

### Today Strategy Energy Explanation

`GET /api/v1/today/strategy` 在 P3 新增 `energy` 解释块：

```json
{
  "energy": {
    "has_data": true,
    "metric_date": "2026-05-17",
    "energy_score": 83,
    "energy_level": "high",
    "recommended_mode": "deep_work",
    "explanation": "今天精力较好，适合保护深度任务；当前只作为解释，不会自动增加任务量。",
    "applied_to_plan": false,
    "source": "energy_daily_metric"
  }
}
```

Rules:

- `energy` 只解释当天策略，不触发 replan。
- 当前 `applied_to_plan=false`，表示 Energy 尚未参与 Today 排序。
- 无 Energy 数据时返回 `has_data=false`、`source=none`，并说明 Today 仍基于任务价值、截止时间和依赖。
- 前端不要把该字段放到 Today 首屏驾驶舱；它属于 Strategy Detail 的补充解释。

### Health worker placeholder

Celery tasks:

```text
health.sync_energy_connection(connection_id, metrics=null, end_date=null, days=7)
health.sync_ready_energy_connections(limit=50)
```

Worker rules:

- 只处理 `source_type=health`、`status=connected`、`sync_enabled=true` 的连接。
- `metrics=null` 时通过 health provider adapter 拉取日级聚合数据；当前 fake adapter 从 `connection_metadata.fake_energy_metrics` 读取。
- `metrics=[...]` 时使用调用方传入的规范化 daily metric。
- Health worker 写入 `EnergyDailyMetric`，不会创建 `ExternalCaptureImport`、`CaptureInput` 或 `InboxItem`。
- 同步会记录 `DataSourceSyncRun` 和 `DATA_SOURCE_SYNCED` / `DATA_SOURCE_SYNC_SKIPPED` / `DATA_SOURCE_SYNC_FAILED`。
- fake provider 可读取 `connection_metadata.fake_next_cursor` 作为下一次 cursor。

Fake health metadata example:

```json
{
  "connection_metadata": {
    "fake_energy_metrics": [
      {
        "external_metric_id": "health-2026-05-17",
        "metric_date": "2026-05-17",
        "sleep_minutes": 450,
        "sleep_quality_score": 82,
        "stress_score": 30,
        "energy_score": 83
      }
    ],
    "fake_next_cursor": "health-cursor-2"
  }
}
```

## 8. 当前安全边界

- 仍使用开发态 `X-User-Id` 用户上下文。
- 不保存外部平台 access token / refresh token。
- 当前不接真实第三方 API。
- 外部来源任务只进入 Capture / Inbox，由用户确认后再生成 Task / Goal。

## 8. 后续 P3

- 真实 Calendar / Email provider adapter。
- 定时调度与失败重试策略。
- Health data import。
- Energy Dashboard。
- Notification / Reminder Center。
- 独立来源详情接口。
