# Iteration: P3 Data Source Sync Runs

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Data Source worker 增加 `DataSourceSyncRun` 观测模型和轻量读取接口，记录每次同步尝试的成功、跳过、失败、cursor、item 数和 retry 元数据。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

前两轮已经建立 connector worker placeholder 和 fake provider adapter。当前同步结果只通过 `ActivityEvent` 留痕，适合行为时间线，但不够承接真实 provider 接入后的失败原因、耗时、cursor 和 retry 判断。因此本轮补一张轻量观测表。

### 目标

- 新增 `DataSourceSyncRun` 模型和迁移。
- 每次同步成功、跳过、失败都生成 sync run。
- 失败时记录 `retryable`、`next_retry_at`、`error_message`。
- 增加只读接口查看某个连接最近 sync runs。

### 非目标

- 不实现自动重试调度。
- 不接真实 provider。
- 不保存外部 token 或完整第三方响应。
- 不改变 ExternalCaptureImport / Capture / Inbox 的确认链路。

---

## 3. 产品约束对齐

### 核心路径

```text
Provider -> Worker -> SyncRun -> ExternalCaptureImport -> Capture -> Inbox
```

- [x] Capture
- [x] Inbox
- [ ] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

SyncRun 是幕后观测能力，不增加用户操作负担。它让系统更可信：同步失败时能解释原因，但不会把技术细节推到 Today 或 Focus 里。

### 设计护栏

- [x] 不让 Today 变成复杂驾驶舱
- [x] 不让 Task Detail 变成信息仓库
- [x] 不让 Focus 变成控制面板
- [x] 不让洞察和解释抢走行动感
- [x] 不让“聪明”压过“可信”

---

## 4. 需求范围

### 功能清单

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| SyncRun model | 记录同步尝试 | Must | 成功 / 跳过 / 失败 |
| Failed run retry metadata | 记录 retryable / next_retry_at | Must | 不自动重试 |
| SyncRun list API | 查看连接最近同步记录 | Should | 只读 |
| Worker event linking | ActivityEvent payload 带 sync_run_id | Should | 可追踪 |
| Batch failure isolation | 批量同步中单连接失败不拖停整批 | Should | 返回 partial_failed |

### 用户故事

```text
作为 Chronos 用户，
我希望数据接入出现问题时系统能知道发生了什么，
以便后续能给出可信、克制的状态说明，而不是静默失败。
```

```text
作为后端开发者，
我希望每次 Data Source 同步都有结构化记录，
以便真实 provider 接入后能调试失败、cursor 和 item 导入结果。
```

```text
作为系统，
我希望失败同步能标记是否可重试，
以便后续调度器可以基于同一模型实现 retry。
```

### 主要流程

```text
sync_connection
-> create DataSourceSyncRun(running)
-> skip / provider fetch / import items
-> update run(succeeded | skipped | failed)
-> write ActivityEvent with sync_run_id

sync_ready_connections
-> iterate ready connections
-> failed connection records failed run
-> continue next connection
-> return partial_failed + failed_connection_count when needed
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [x] Models
- [x] Schemas
- [x] Workers
- [ ] Agents
- [ ] Storage
- [x] DB Migration
- [x] Tests

### 数据模型变更

```text
DataSourceSyncRun {
  id
  user_id
  data_source_connection_id
  source_type
  provider
  status
  trigger
  attempt
  max_attempts
  retryable
  next_retry_at
  skip_reason
  error_message
  processed_count
  imported_count
  reused_count
  fetched_from_provider
  provider_mode
  sync_cursor_before
  sync_cursor_after
  started_at
  finished_at
  duration_ms
  metadata
}
```

### 状态机变更

```text
running -> succeeded
running -> skipped
running -> failed
```

### 事件变更

- `DATA_SOURCE_SYNCED`
- `DATA_SOURCE_SYNC_SKIPPED`
- `DATA_SOURCE_SYNC_FAILED`

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/data-sources/{connection_id}/sync-runs` | 查看最近同步记录 | query `limit`, `offset` | `DataSourceSyncRunResponse[]` |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [x] 不涉及
- [ ] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

说明：本轮是非 AI worker 观测能力，不创建 AIJob。

---

## 7. 验收标准

### 功能验收

- [x] 同步成功生成 `succeeded` run。
- [x] 跳过同步生成 `skipped` run。
- [x] 同步失败生成 `failed` run，并记录 retry 元数据。
- [x] API 可读取当前用户连接的 sync runs。
- [x] 批量同步遇到单个失败连接时继续处理后续连接。

### 数据验收

- [x] 记录 cursor before / after。
- [x] 记录 processed / imported / reused 计数。
- [x] ActivityEvent payload 带 `sync_run_id`。
- [x] user isolation 正确。

### 体验验收

- [x] 不增加 Today / Focus 复杂度。
- [x] 不绕过 Inbox。
- [x] 不暴露外部 token 或完整第三方响应。

---

## 8. 测试计划

### 单元测试

- [x] success run。
- [x] skipped run。
- [x] failed run + retry metadata。
- [x] batch partial failure isolation。

### API 测试

- [x] `GET /data-sources/{id}/sync-runs` 返回最近 runs。
- [x] other user 访问返回 404。

### 集成测试

- [x] Alembic SQL 生成。
- [x] 真实 DB upgrade。

### 手动验证

```text
1. 创建 email fake connection。
2. sync_connection。
3. GET /data-sources/{id}/sync-runs。
4. 检查 status / cursor / counts / retryable。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 过早做复杂调度系统 | P3 复杂度膨胀 | 本轮只记录 retry 元数据，不自动重试 |
| ActivityEvent 和 SyncRun 重复 | 数据边界混乱 | Event 做时间线，SyncRun 做结构化 worker 观测 |
| 记录过多外部数据 | 泄露或变成信息仓库 | 不保存 token 或完整第三方响应 |

### 关键取舍

- 取舍 1：SyncRun status 使用字符串，避免为早期状态机新增 PostgreSQL enum。
- 取舍 2：失败只记录 retryable 和 next_retry_at，不新增调度器。
- 取舍 3：读取接口只按 connection 返回最近 run，不做全局运维后台。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 DataSourceSyncRun | ActivityEvent 不适合作 worker 结构化观测 | 后续 retry / provider 调试有承接 |
| 2026-05-17 | 不自动重试 | 避免早期 worker 系统复杂化 | 后续可基于 retryable 补调度 |
| 2026-05-17 | 批量同步失败隔离 | 单个 provider 或 item 失败不应拖停整批连接 | worker 返回 `partial_failed` 并继续处理 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增模型和迁移 | `app/models/data_source_sync_run.py`, `alembic/versions/20260517_0010_data_source_sync_runs.py` | sync run |
| 2026-05-17 | 同步服务记录 run | `app/services/data_source_sync_service.py` | success / skip / fail |
| 2026-05-17 | 新增响应 schema/API | `app/schemas/data_sources.py`, `app/api/v1/data_sources.py` | sync-runs |
| 2026-05-17 | 补测试 | `tests/test_data_source_sync_service.py`, `tests/test_data_source_api.py` | service / API / batch failure |
| 2026-05-17 | 更新文档 | P3 contract / architecture | SyncRun 说明 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_data_source_sync_service tests.test_data_source_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head --sql`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 自动重试调度。
- [ ] 真实 provider 失败类型映射。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- Retry scheduler / retry due sync runs。
- Provider error taxonomy。
- Health / Energy import foundation。
