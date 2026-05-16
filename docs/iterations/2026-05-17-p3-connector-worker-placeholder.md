# Iteration: P3 Connector Worker Placeholder

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

建立 Calendar / Email connector worker 的后端占位同步链路：读取 Data Source 连接状态，消费规范化外部 item，通过 ExternalCaptureImport 进入 Capture / Inbox。

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

P3 已完成 Data Source 连接状态底座、External Capture Import、Task Detail Source Context。下一步需要把“后续真实 Calendar / Email connector”将要调用的 worker/service 路径先搭起来，确保外部来源仍然遵守 `Capture -> Inbox -> Task` 的确认链路。

### 目标

- 新增 Data Source Sync service，按连接状态决定是否可同步。
- 新增 Celery tasks：同步单个连接、同步当前 ready 连接。
- 同步 item 通过 ExternalCaptureImport 幂等进入 Capture / Inbox。
- 同步后更新 `last_sync_at` / `sync_cursor`，并记录 worker 事件。

### 非目标

- 不实现真实 OAuth。
- 不调用 Google Calendar / Gmail / Outlook API。
- 不做定时调度、重试队列、速率限制。
- 不让 worker 直接生成 Task 或跳过 Inbox 确认。

---

## 3. 产品约束对齐

### 核心路径

```text
Calendar / Email -> Worker -> Capture -> Inbox -> Today -> Task Detail -> Focus
```

- [x] Capture
- [x] Inbox
- [ ] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

该迭代把外部复杂度藏在系统后面，只把可确认的任务候选放入 Inbox。用户不会感知到复杂同步流程，只会看到可控、可确认的输入池。

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
| Sync single connection | 同步一个 DataSourceConnection | Must | Calendar / Email |
| Sync ready connections | 批量同步 ready 连接 | Should | 先无定时调度 |
| Import normalized items | 将规范化 item 交给 ExternalCaptureImport | Must | 幂等 |
| Sync events | 记录 synced / skipped worker 事件 | Must | 审计与可观察 |

### 用户故事

```text
作为 Chronos 用户，
我希望连接日历或邮箱后，系统能把潜在任务放入 Inbox 等我确认，
以便外部信息不会直接变成压力或打乱今天的安排。
```

```text
作为后续 connector 开发者，
我希望有稳定的 worker/service 同步入口，
以便真实 Google Calendar / Gmail adapter 只负责拉取外部 item，而不需要重写 Chronos 导入链路。
```

```text
作为系统，
我希望同步过程记录 worker 事件和 cursor，
以便后续可以追踪同步结果、失败原因和幂等导入状态。
```

### 主要流程

```text
DataSourceConnection(connected + sync_enabled)
-> data_source.sync_connection
-> normalized external items
-> ExternalCaptureImport
-> CaptureInput(input_type=external)
-> InboxItem(pending)
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [ ] Schemas
- [x] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

- `DATA_SOURCE_SYNCED`
- `DATA_SOURCE_SYNC_SKIPPED`

事件约束：

- `actor_type=system`
- `source=worker`
- entity 为对应 `DataSourceConnection`

### API 变更

无前端 API 变更。本轮新增内部 Celery tasks：

| Task | 用途 | 输入 | 输出 |
| --- | --- | --- | --- |
| `data_source.sync_connection` | 同步单个连接 | `connection_id`, `items`, `sync_cursor` | sync result |
| `data_source.sync_ready_connections` | 同步 ready 连接 | `limit` | batch result |

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

说明：本轮是非 AI worker，不创建 AIJob；AIJob 约束仍适用于后续 AI Agent 类任务。

---

## 7. 验收标准

### 功能验收

- [x] connected + sync_enabled 的 Calendar / Email 连接可以同步。
- [x] Health / paused / disabled 连接不会导入外部 item。
- [x] 重复外部 item 复用已有 ExternalCaptureImport。
- [x] Celery task 返回 JSON-friendly result。

### 数据验收

- [x] 同步成功更新 `last_sync_at`。
- [x] 传入 `sync_cursor` 时更新连接 cursor。
- [x] 导入结果落入 Capture / Inbox，不直接生成 Task。
- [x] 同步事件记录 `system + worker` 来源。

### 体验验收

- [x] 用户仍保留 Inbox 确认权。
- [x] Today 不因外部同步变复杂。
- [x] Task Detail 不展示完整外部 payload。

---

## 8. 测试计划

### 单元测试

- [x] Service 同步成功路径。
- [x] Service 幂等导入路径。
- [x] Service skip 路径。

### Worker 测试

- [x] 单连接 Celery task 可直接运行并返回 JSON-friendly result。
- [x] ready connections task 只处理 Calendar / Email。

### 集成测试

- [ ] DB migration：本轮无 migration。
- [ ] 真实 provider：本轮不涉及。

### 手动验证

```text
1. 创建 calendar/email data source。
2. 调用 sync_connection 并传入规范化 item。
3. 检查 ExternalCaptureImport / CaptureInput / InboxItem。
4. 检查 DataSourceConnection last_sync_at / sync_cursor。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Worker 被误解为真实第三方同步 | 产品/工程预期错位 | 文档明确 placeholder，不接真实 API |
| 外部 item 绕过用户确认 | 破坏 Chronos 控制感 | 只走 ExternalCaptureImport -> Capture -> Inbox |
| 批量同步无重试策略 | 后续真实接入稳定性不足 | 后续单独做调度、失败重试、provider adapter |

### 关键取舍

- 取舍 1：先做规范化 item 的同步入口，不在本轮接 OAuth/provider。
- 取舍 2：同步事件用 ActivityEvent 记录，不新增 SyncRun 表，避免 P3 早期过重。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | connector worker 只消费规范化 item | 保持 P3 小步可验证 | 后续 adapter 可复用同一入口 |
| 2026-05-17 | 非 AI worker 不创建 AIJob | AIJob 只约束 AI 任务 | Data source sync 用 ActivityEvent 记录 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增同步 service | `app/services/data_source_sync_service.py` | 连接过滤、幂等导入、事件 |
| 2026-05-17 | 新增 Celery tasks | `app/workers/tasks.py` | 单连接 / ready 连接同步 |
| 2026-05-17 | 新增测试 | `tests/test_data_source_sync_service.py` | service + worker |
| 2026-05-17 | 更新文档 | `docs/chronos-p3-frontend-api-contract.md`, `docs/chronos-backend-architecture-v1.md` | P3 worker 合同 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_data_source_sync_service`
- [x] `uv run python -m unittest tests.test_data_source_sync_service tests.test_external_capture_import_services tests.test_external_capture_import_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

### 未验证

- [ ] 真实 Google Calendar / Gmail / Outlook provider。
- [ ] 定时调度、失败重试、速率限制。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- Calendar provider adapter 接口与假 provider。
- Email provider adapter 接口与假 provider。
- Worker retry / sync run 观测模型。
