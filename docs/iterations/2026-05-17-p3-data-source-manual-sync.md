# Iteration: P3 Data Source Manual Sync

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增单连接手动同步接口，让用户或前端在 Settings 中明确触发某个数据源同步，而不是等待后台调度。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

P3 已有 sync summary 告诉 Settings 哪些连接正常或需要关注，但用户还缺一个明确、可控的“立即同步这个连接”动作。这个动作应该是用户触发，不是后台自动调度，也不能绕过 Capture / Inbox 或 Energy 的边界。

### 目标

- 新增 `POST /api/v1/data-sources/{connection_id}/sync`。
- Calendar / Email 连接同步后进入 Capture / Inbox。
- Health 连接同步后进入 EnergyDailyMetric。
- 返回统一 manual sync response。
- P3 smoke 覆盖手动同步。

### 非目标

- 不做后台自动重试。
- 不接真实 OAuth。
- 不绕过 Inbox 自动确认任务。
- 不创建 Today / Reminder。

---

## 3. 产品约束对齐

### 核心路径

```text
Me / Settings -> Manual Sync -> Capture / Inbox or Energy
```

- [x] Capture
- [x] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

手动同步是用户明确触发的动作，保留控制感；同步结果只进入输入层或精力层，不直接替用户安排任务。

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
| Manual sync API | 单连接立即同步 | Must | 用户触发 |
| Calendar / Email route | 复用 external capture import sync service | Must | 进入 Capture / Inbox |
| Health route | 复用 health sync service | Must | 进入 EnergyDailyMetric |
| User isolation | 不能同步他人连接 | Must | 404 |
| Smoke alignment | P3 smoke 覆盖 manual sync | Must | 防回归 |

### 用户故事

```text
作为 Chronos 用户，
我希望在 Settings 中手动同步某个数据源，
以便我能主动更新上下文，而不是等待后台调度。
```

```text
作为前端开发者，
我希望手动同步返回统一结构，
以便同一个 Settings 操作可以兼容 Calendar / Email / Health。
```

### 主要流程

```text
POST /data-sources/{connection_id}/sync
-> verify user owns connection
-> route calendar/email to data source sync service
-> route health to health sync service
-> return compact sync result
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [ ] Models
- [x] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

复用既有事件：

- `DATA_SOURCE_SYNCED`
- `DATA_SOURCE_SYNC_SKIPPED`
- `DATA_SOURCE_SYNC_FAILED`
- `EXTERNAL_CAPTURE_IMPORTED`

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/data-sources/{connection_id}/sync` | 手动同步单连接 | 无 | `DataSourceManualSyncResponse` |

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

说明：本轮不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] Calendar / Email 手动同步可导入 external captures。
- [x] Health 手动同步可导入 energy metrics。
- [x] 跨用户同步返回 404。
- [x] 手动同步返回统一 response。
- [x] 不创建 Today / Reminder，不自动确认 Inbox。

### 数据验收

- [x] 不新增 schema。
- [x] 同步仍写 DataSourceSyncRun。
- [x] 不暴露 external payload。

### 体验验收

- [x] 用户有明确控制入口。
- [x] Settings 不变成复杂调度控制台。

---

## 8. 测试计划

### 单元测试

- [x] data source service manual sync calendar / health / isolation。

### API 测试

- [x] manual sync API。

### 集成测试

- [x] `uv run python scripts/smoke_p3_natural_growth_loop.py`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| API 同步可能变慢 | 真实 provider 下请求耗时 | 当前 fake provider；真实 provider 前再改成 enqueue job |
| 手动同步被误解成自动排程 | 用户控制感变弱 | 命名为 manual sync，只同步指定 connection |
| Calendar / Email 导入后自动确认 | 破坏 Inbox 缓冲层 | 复用 external import，仍进入 Inbox |

### 关键取舍

本轮先提供明确的同步动作，不引入后台自动 retry 或复杂 job 状态；真实 provider 接入前再决定是否改为异步 enqueue。

---

## 10. Review 记录

### 自检结论

- 与 P3 信息架构一致：数据接入入口在 Me / Settings。
- 与产品人格一致：用户触发、克制、可解释。
- 与工程边界一致：API 调 service，service 根据 source type 路由，不在 router 写业务规则。

### 后续建议

- 真实 provider 接入前，将 manual sync 改为创建 sync job / worker async 执行。
