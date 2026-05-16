# Iteration: P3 Data Source Sync Summary

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 Data Source Sync Summary 只读接口，为 Me / Settings 的数据接入入口提供轻量同步健康度总览。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

P3 已支持数据源连接、sync runs、health sync 和 scheduler contract。但前端 Settings 如果只看 catalog 和单连接 sync runs，无法快速展示“哪些接入正常、哪些需要用户注意”。需要一个轻量总览，避免 Settings 拼接大量底层资源。

### 目标

- 新增 `GET /api/v1/data-sources/sync-summary`。
- 返回 connected / sync_enabled / attention 计数。
- 返回每个连接的 latest run 状态、导入数量、retry 信息和 attention reason。
- 不触发同步，不暴露外部 payload。
- P3 smoke 覆盖 sync summary。

### 非目标

- 不新增数据模型。
- 不做自动重试。
- 不接真实 provider。
- 不展示 sync run 全量历史。

---

## 3. 产品约束对齐

### 核心路径

```text
Me / Settings -> Data Source Sync Summary -> User Attention
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

Summary 只给用户“是否正常、是否需要处理”的轻量判断，不把 Settings 变成复杂运维面板。

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
| Sync summary service | 聚合连接和最新 sync run 状态 | Must | 只读 |
| Sync summary API | `GET /data-sources/sync-summary` | Must | Settings 可用 |
| Attention reason | 返回 paused / disconnected / needs_reauth / sync_disabled / latest_sync_failed | Must | 简单可解释 |
| Smoke alignment | P3 smoke 校验 summary | Must | 防回归 |

### 用户故事

```text
作为 Chronos 用户，
我希望在 Settings 里快速知道数据接入是否正常，
以便有问题时能处理连接，而不是看到一堆同步日志。
```

```text
作为前端开发者，
我希望有一个轻量 sync summary，
以便 Settings 不需要拼接 catalog、connections 和 sync runs 才能渲染状态。
```

### 主要流程

```text
GET /data-sources/sync-summary
-> list user connections
-> attach latest sync run per connection
-> derive attention reason
-> return summary counts and compact items
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

无。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/data-sources/sync-summary` | 数据接入同步健康度总览 | 无 | `DataSourceSyncSummaryResponse` |

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

说明：本轮只读聚合接口，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] 返回 connected_count、sync_enabled_count、attention_count。
- [x] 返回每个连接的 latest_run_status、retryable、next_retry_at、imported_count、attention_reason。
- [x] paused / disconnected / needs_reauth / sync_disabled / latest failed 能被标记为 needs_attention。
- [x] 接口不触发同步。
- [x] 用户隔离正确。

### 数据验收

- [x] 不新增 schema。
- [x] 不写数据库。
- [x] 不暴露 external_payload。

### 体验验收

- [x] Settings 可用一个轻量接口表达接入健康度。
- [x] 不把同步日志暴露成复杂控制台。

---

## 8. 测试计划

### 单元测试

- [x] data source service sync summary。

### API 测试

- [x] data source sync summary API。

### 集成测试

- [x] `uv run python scripts/smoke_p3_natural_growth_loop.py`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| N+1 查询 latest run | 连接数量增长后性能一般 | P3 连接数很小，后续可优化窗口函数 |
| attention reason 过于简单 | 不能表达复杂故障 | 当前面向 Settings 轻量状态，详细日志仍用 sync-runs |
| Summary 被当成运维面板 | 产品变重 | 只返回 compact items，不返回 payload 和完整历史 |

### 关键取舍

本轮优先给 Settings 一个克制、可解释的健康度入口，不做复杂同步控制台。

---

## 10. Review 记录

### 自检结论

- 与 P3 信息架构一致：数据接入属于 Me / Settings，不作为一级导航。
- 与产品人格一致：只暴露必要状态，不制造压力。
- 与工程规范一致：页面聚合接口由 service 生成，不让前端拼多个资源。

### 后续建议

- 后续可增加手动 retry 单连接 API，但需要明确用户触发与后台自动重试边界。
