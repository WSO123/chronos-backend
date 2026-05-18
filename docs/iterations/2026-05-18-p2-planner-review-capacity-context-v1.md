# Iteration: P2 Planner Review Capacity Context v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 关联 Commit：待提交

---

## 1. 迭代摘要

让 Daily Planner Agent 在 Strategy Detail 的审阅里读懂今日可用时间、容量来源和滚动压力，但仍只做 critique / suggestion，不接管 Planning Engine 排序。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

上一轮 Daily Available Time v1 让用户可以在 Today replan 时设置今日可用分钟数，Planning Engine 会据此收敛主执行序列。缺口在于：Daily Planner Agent 的 review 仍主要读取候选任务和 score factors，不能稳定表达“这份计划为什么符合今天的可用时间边界”。

### 目标

- 给 Daily Planner Agent 增加只读 `review_context`。
- `review_context` 包含 capacity、workload 和 agent boundaries。
- mock / provider metadata 都能看到同一份上下文，便于后续真实 provider 调试。
- Planner Review 能生成尊重手动可用时间和滚动边界的轻量建议。

### 非目标

- 不允许 Daily Planner Agent 重排任务。
- 不允许 Daily Planner Agent 移动 section。
- 不允许 Daily Planner Agent 创建、完成、延后或修改任务。
- 不做日历、提醒、P3/P4 或前端页面。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Task Detail -> Focus
```

本轮增强的是 Today 的解释层，帮助用户相信“今天做得出来”，但不增加 Today 首屏复杂度。

### 用户故事

```text
作为一个今天时间有限的用户，
我希望 AI 审阅能明确承认我今天只有多少可用时间，
以便我知道当前主序列不是随便排序，而是按真实容量收敛出来的。
```

```text
作为 Planning Engine，
我希望 Daily Planner Agent 只能读取只读容量上下文，
以便 LLM 能补充自然解释，但不能绕过确定性排序边界。
```

### 设计护栏

- [x] 不让 Today 变成复杂驾驶舱。
- [x] 不让 Task Detail 变成信息仓库。
- [x] 不让 Focus 变成控制面板。
- [x] 不让洞察和解释抢走行动感。
- [x] 不让“聪明”压过“可信”。

---

## 4. 需求范围

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Planner review context | Daily Planner Agent 接收 `review_context` | Must | 只读 |
| Capacity-aware mock review | mock output 能识别手动可用时间和低精力容量收敛 | Must | 本地稳定 |
| AIJob observability | `AIJob.job_metadata` 记录 capacity / workload context | Should | 便于真实 provider 排障 |
| Prompt 对齐 | 中文 prompt 明确审阅容量边界，不改排序 | Must | 延续产品人格 |

### 主要流程

```text
Planning Engine 生成 deterministic plan
-> StrategySnapshot.score_factors 生成 capacity/workload
-> Daily Planner Agent 收到只读 review_context
-> Agent 返回 review_summary / suggestions
-> Strategy Detail 展示 planner_review
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [ ] Schemas
- [ ] Workers
- [x] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无。

### Agent 边界

`review_context.boundaries` 固化本轮约束：

```json
{
  "source_of_truth": "planning-engine-v1",
  "can_reorder": false,
  "can_move_sections": false,
  "can_mutate_tasks": false,
  "output_surface": "strategy_detail_review_only"
}
```

### 状态机变更

无。

### 事件变更

无。

---

## 6. 验收标准

- [x] Daily Planner Agent metadata 包含 `review_context`。
- [x] Planning Service 传入 capacity / workload / boundaries。
- [x] AIJob metadata 记录 `review_context_version`、`capacity_context`、`workload_context`。
- [x] 手动可用时间场景下，Planner Review 能返回 `manual_capacity_respected`。
- [x] Agent 仍不能重排或移动 section。

---

## 7. 测试计划

```bash
uv run python -m unittest tests.test_daily_planner_agent tests.test_today_services
.venv/bin/python -m compileall app tests scripts
uv run python -m unittest discover -s tests
git diff --check
```

---

## 8. 防偏航 Review

- 本轮仍然服务 P2 Strategy Detail / AI Agent 解释层。
- 没有新增 P3/P4、商业化、前端页面或高级 auth。
- 没有让 LLM 直接排序。
- 没有绕过 Capture / Inbox。
- 没有把 Today 首屏做重。

---

## 9. 下一轮建议

P2 User Preference Learning v1：把用户对 Planner Review 建议的接受 / 忽略记录成轻量反馈，后续只影响解释和权重信号，不让 LLM 直接修改计划。
