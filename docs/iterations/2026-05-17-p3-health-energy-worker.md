# Iteration: P3 Health Energy Worker Placeholder

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Health 数据源增加 fake provider adapter 和 worker 占位同步能力，把睡眠 / 压力 / 精力日级数据导入 `EnergyDailyMetric`，打通 Health -> Energy Dashboard 的后台链路。

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

上一轮已建立 `EnergyDailyMetric` 和 Energy Dashboard，但数据只能通过 API upsert。P3 的自然生长模块要求 Health 数据能作为睡眠 / 压力输入，因此本轮补 Health worker 占位和 fake provider adapter。

### 目标

- 新增 Health fake provider adapter，从 connection metadata 读取 `fake_energy_metrics`。
- 新增 `HealthSyncService`，将 daily metrics 导入 `EnergyDailyMetric`。
- 新增 Celery task：`health.sync_energy_connection` / `health.sync_ready_energy_connections`。
- 复用 `DataSourceSyncRun` 记录成功、跳过、失败。

### 非目标

- 不接真实 HealthKit / Google Fit API。
- 不保存原始健康平台 payload。
- 不让 Health 数据进入 Capture / Inbox。
- 不影响 Today 排序。

---

## 3. 产品约束对齐

### 核心路径

```text
Health Provider -> Worker -> EnergyDailyMetric -> Energy Dashboard
```

- [ ] Capture
- [ ] Inbox
- [ ] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

Health worker 是幕后数据接入能力，只为 Energy Dashboard 提供克制解释，不直接把健康状态转成压力或任务。

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
| Health fake provider | 读取 fake_energy_metrics | Must | apple_health / google_fit |
| Health sync service | 导入 EnergyDailyMetric | Must | 不进 Capture |
| Worker tasks | 单连接 / ready batch 同步 | Must | Celery task |
| SyncRun observability | 成功 / 跳过 / 失败记录 | Should | 复用 DataSourceSyncRun |

### 用户故事

```text
作为 Chronos 用户，
我希望健康数据能自然进入 Energy Dashboard，
以便系统更理解我今天的状态，但不会把健康数据变成额外任务压力。
```

```text
作为后端开发者，
我希望 Health 导入链路与 Calendar / Email 导入链路分开，
以便睡眠 / 压力数据不会误进 Capture / Inbox。
```

### 主要流程

```text
health.sync_energy_connection
-> fetch fake_energy_metrics or use explicit metrics
-> upsert EnergyDailyMetric(source=health_import)
-> update DataSourceSyncRun
-> Energy Dashboard reads metrics
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

无新增模型，复用：

```text
DataSourceConnection
DataSourceSyncRun
EnergyDailyMetric
```

### 状态机变更

```text
DataSourceSyncRun: running -> succeeded
DataSourceSyncRun: running -> skipped
DataSourceSyncRun: running -> failed
```

### 事件变更

- `DATA_SOURCE_SYNCED`
- `DATA_SOURCE_SYNC_SKIPPED`
- `DATA_SOURCE_SYNC_FAILED`

### API 变更

无新增 HTTP API。

Worker:

| Task | 用途 |
| --- | --- |
| `health.sync_energy_connection` | 同步单个 Health connection |
| `health.sync_ready_energy_connections` | 批量同步 ready Health connections |

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

说明：本轮是 Health worker 数据接入占位，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] 显式 metrics 可导入 `EnergyDailyMetric`。
- [x] fake provider 可从 connection metadata 读取日级 metrics。
- [x] ready worker 只处理 Health connection。
- [x] 非 Health / paused / disabled connection 会跳过。

### 数据验收

- [x] 导入结果写入 `DataSourceSyncRun`。
- [x] ActivityEvent payload 带 `sync_run_id`。
- [x] 不创建 `ExternalCaptureImport` / `CaptureInput` / `InboxItem`。

### 体验验收

- [x] 不改变 Today 排序。
- [x] 不把健康数据变成任务压力。
- [x] Energy Dashboard 可读取导入后的聚合数据。

---

## 8. 测试计划

### 单元测试

- [x] explicit metrics import。
- [x] fake provider metadata import。
- [x] skip unsupported / paused connection。
- [x] worker json-ready result。
- [x] ready worker filters health only。

### API 测试

- [x] 复用上一轮 Energy Dashboard API 测试。

### 集成测试

- [x] 全量测试。
- [x] 编译检查。
- [x] Alembic head 检查。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Health 和 Calendar / Email 导入链路混淆 | 健康数据进入 Inbox | 独立 HealthSyncService，只写 EnergyDailyMetric |
| fake provider 被误认为真实接入 | 产品预期偏差 | 文档明确真实平台待后续 |
| 同步结果不可观测 | 后续 provider 调试困难 | 复用 DataSourceSyncRun |

### 关键取舍

- 取舍 1：不复用 Calendar / Email 的 ExternalCaptureImport 链路。
- 取舍 2：fake provider 只读取日级聚合数据，不模拟原始设备样本。
- 取舍 3：worker 只做导入，不影响 Today。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Health 数据进入 EnergyDailyMetric | Health 是精力辅助输入，不是任务来源 | 保持 Capture / Inbox 边界清晰 |
| 2026-05-17 | Health worker 复用 DataSourceSyncRun | 同步观测模型已存在 | 统一 Settings / 调试观测能力 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 fake health provider | `app/providers/health.py` | fake_energy_metrics |
| 2026-05-17 | 新增同步服务 | `app/services/health_sync_service.py` | health -> energy |
| 2026-05-17 | 新增 worker task | `app/workers/tasks.py` | Celery |
| 2026-05-17 | 补测试 | `tests/test_health_sync_service.py` | service / worker |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | Health worker 合同 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_health_sync_service tests.test_energy_services tests.test_energy_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 真实 HealthKit / Google Fit。
- [ ] 自动定时调度。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- Today Strategy Detail 增加 Energy explanation，但仍不直接重排。
- Reminder Center P3 基础提醒模型。
- Notification settings / reminder worker。
