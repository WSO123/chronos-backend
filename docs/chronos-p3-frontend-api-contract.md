# Chronos P3 Frontend API Contract

日期：2026-05-16
状态：P3 foundation contract

## 1. 目的

本文档沉淀 P3 自然生长模块的第一批后端接口合同。

当前 P3 只完成数据源连接状态底座，用来承接：

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
| Disconnect Data Source | `POST /api/v1/data-sources/{connection_id}/disconnect` | Ready |
| Calendar Sync Worker | - | Not Started |
| Email Sync Worker | - | Not Started |
| Health / Energy Data Import | - | Not Started |
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

## 4. 当前安全边界

- 仍使用开发态 `X-User-Id` 用户上下文。
- 不保存外部平台 access token / refresh token。
- 不直接导入外部任务。
- 外部来源任务后续应进入 Capture / Inbox，由用户确认后再生成 Task / Goal。

## 5. 后续 P3

- Calendar / Email connector worker。
- Health data import。
- Energy Dashboard。
- Notification / Reminder Center。
- 来源内容关联到 Task Detail。
