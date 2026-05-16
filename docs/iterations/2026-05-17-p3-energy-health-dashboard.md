# Iteration: P3 Energy / Health Dashboard Foundation

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

建立 Energy / Health 的日级数据底座和只读 Dashboard API，让 Me -> Energy Dashboard 可以展示睡眠、压力、精力趋势，并为后续 Today 精力辅助排序预留输入。

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

P3 已具备 Health 数据源连接状态底座，但睡眠 / 压力数据仍没有专用模型。产品信息架构中 Energy Dashboard 属于 Me 的二级反馈层，主要服务精力趋势、任务类型建议和后续 Today 的解释性输入。

### 目标

- 新增 `EnergyDailyMetric` 日级聚合模型。
- 支持写入 / 更新每日睡眠、压力、精力数据。
- 提供 `GET /energy/dashboard` 返回趋势、今日摘要和任务类型建议。
- 明确 Health 数据不进入 Capture / Inbox，不直接生成 Task。

### 非目标

- 不接真实 HealthKit / Google Fit。
- 不实现实时健康样本存储。
- 不改变 Today 排序。
- 不生成 AI 洞察或 LLM 调用。

---

## 3. 产品约束对齐

### 核心路径

```text
Health -> Energy Dashboard -> Today strategy input later
Me -> Energy Dashboard
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

Energy Dashboard 只提供克制的状态说明和轻量任务类型建议，不制造健康焦虑，不把复杂生理数据推给 Today。

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
| EnergyDailyMetric | 日级睡眠 / 压力 / 精力聚合 | Must | 非原始健康样本 |
| Upsert API | 写入或更新某日 metric | Must | 手动或后续 worker 复用 |
| Dashboard API | 趋势、摘要、任务类型建议 | Must | 只读 |
| Health connection validation | 可关联 owned health connection | Should | 防止跨用户 / 错源 |

### 用户故事

```text
作为 Chronos 用户，
我希望在 Me 中看到睡眠、压力和精力趋势，
以便理解今天适合轻量推进还是深度专注。
```

```text
作为后端开发者，
我希望 Health 数据有专用聚合模型，
以便后续真实健康平台接入时不会误走 Capture / Inbox。
```

### 主要流程

```text
PUT /energy/daily-metrics
-> validate user and optional health connection
-> upsert EnergyDailyMetric
-> GET /energy/dashboard
-> return summary + trends + task_match + suggestions
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [x] Models
- [x] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [x] DB Migration
- [x] Tests

### 数据模型变更

```text
EnergyDailyMetric {
  id
  user_id
  data_source_connection_id
  metric_date
  source
  sleep_minutes
  sleep_quality_score
  stress_score
  energy_score
  note
  metadata
}
```

### 状态机变更

无。

### 事件变更

无。当前 Energy 是 Dashboard 数据底座，不写 ActivityEvent，避免把健康 check-in 混入执行行为时间线。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| PUT | `/api/v1/energy/daily-metrics` | 写入每日 Energy metric | `EnergyDailyMetricUpsert` | `EnergyDailyMetricResponse` |
| GET | `/api/v1/energy/dashboard` | 获取 Energy Dashboard | query `end_date`, `days` | `EnergyDashboardResponse` |

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

说明：本轮无 LLM 调用。

---

## 7. 验收标准

### 功能验收

- [x] 可写入日级 sleep / stress / energy metric。
- [x] 未传 energy_score 时可轻量推导。
- [x] Dashboard 返回趋势、今日摘要、任务类型建议。
- [x] 可选关联的 data source 必须是当前用户的 Health 连接。

### 数据验收

- [x] 同一用户同一天 upsert 而不是重复插入。
- [x] 用户数据隔离正确。
- [x] 不保存原始健康平台 payload 或 token。

### 体验验收

- [x] 不改变 Today 排序。
- [x] 不把健康数据变成任务压力。
- [x] 建议文案保持克制。

---

## 8. 测试计划

### 单元测试

- [x] upsert + derived energy score。
- [x] same-day update。
- [x] owned health connection validation。
- [x] dashboard user isolation。

### API 测试

- [x] PUT daily metric + GET dashboard。
- [x] dashboard user isolation。
- [x] empty metric validation。

### 集成测试

- [x] Alembic SQL 生成。
- [x] 真实 DB upgrade。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 过早把健康数据用于 Today 排序 | Today 复杂化、用户压力增加 | 当前只做 Dashboard 和解释性输入 |
| 存原始健康数据 | 隐私和信息仓库风险 | 只存日级聚合，不保存原始 payload |
| 精力推导过度智能化 | “聪明”压过可信 | 使用轻量规则，字段可解释 |

### 关键取舍

- 取舍 1：日级聚合优先，不存原始样本。
- 取舍 2：不写 ActivityEvent，避免健康数据污染执行时间线。
- 取舍 3：Dashboard 先只读，不反向改 Today。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 EnergyDailyMetric | Health 数据不应走 Capture / Inbox | 为 Energy Dashboard 和后续 provider worker 提供底座 |
| 2026-05-17 | Dashboard 不改 Today | 遵守 Today 不复杂化 | 后续接入时需通过策略解释和用户控制 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增模型和迁移 | `app/models/energy.py`, `alembic/versions/20260517_0011_energy_daily_metrics.py` | daily metrics |
| 2026-05-17 | 新增 Energy service/API/schema | `app/services/energy_service.py`, `app/api/v1/energy.py`, `app/schemas/energy.py` | dashboard |
| 2026-05-17 | 补测试 | `tests/test_energy_services.py`, `tests/test_energy_api.py` | service / API |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | Energy API 合同 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_energy_services tests.test_energy_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head --sql`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 真实 HealthKit / Google Fit provider。
- [ ] Energy 对 Today 排序的策略影响。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- Health provider fake adapter / worker，将 `DataSourceConnection(health)` 元数据导入 `EnergyDailyMetric`。
- Today Strategy Detail 增加只读 Energy explanation，不直接改排序。
- Reminder Center P3 基础提醒模型。
