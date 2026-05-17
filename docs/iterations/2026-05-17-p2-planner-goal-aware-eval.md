# Iteration: P2 Planner Goal-Aware Evaluation

> 状态：Done
> 阶段：P2
> 创建日期：2026-05-17
> 负责人：Codex
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让 Planning Engine 读取 Goal 的价值和截止时间，并把多 Goal 竞争、超期 Goal 恢复纳入固定离线评估，避免“高价值目标优先”只停留在文档里。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [P2 Planning Engine v1](./2026-05-17-p2-planning-engine-v1.md)
- [x] [P2 Planner Eval Scenario Expansion](./2026-05-17-p2-planner-eval-scenario-expansion.md)
- [x] [P2 Planner Eval JSONL Compare](./2026-05-17-p2-planner-eval-jsonl-compare.md)

### 背景

Chronos 的核心不是普通 task 排序，而是保护高价值目标不被低价值事项挤掉，并在目标滞后时把可执行的下一步拉回 Today。此前 Planning Engine 已覆盖 Task value、priority、deadline、依赖、用户修正、行为反馈和 Energy，但 Goal 的 value / deadline 还没有真正进入评分。这样会导致文档写着“高价值目标优先”，但实际编排仍主要看 Task 自身。

本轮补上 goal-aware scoring，并把对应场景写入离线 evaluator。

### 目标

- Planning Engine 读取 `Task.goal.value_level`，形成 `goal_value_score`。
- Planning Engine 读取 `Task.goal.deadline`，形成 `goal_urgency_score`。
- 高价值 Goal 下的普通优先级任务可以进入 protected sequence。
- 超期 Goal 下的下一步任务即使没有 task deadline，也可以被拉回 Today 前列。
- Evaluator version 升级为 `p2-planning-engine-eval-v3`。
- 固定场景从 7 个扩展到 9 个。
- JSONL `item_signals` 增加 `goal_value_score` 和 `goal_urgency_score`。

### 非目标

- 不接真实 LLM provider。
- 不改变 Daily Planner Agent structured output。
- 不新增数据库表。
- 不改变 Today 首屏信息密度。
- 不做完整真实用户任务分布模拟。

---

## 3. 产品约束对齐

### 核心路径

```text
Goals -> Goal Detail -> Today -> Task Detail -> Focus
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

本轮让 Chronos 更“有判断”：系统在后台理解 Goal 价值和滞后风险，但 Today 仍只给用户一个清晰的执行顺序和简短理由。复杂度进入 `score_breakdown` 和 Strategy Detail，不进入 Today 首屏。

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
| Goal value score | 高价值 Goal 给关联任务轻量加分 | Must | 不替代 Task value |
| Goal urgency score | Goal deadline 给关联任务轻量紧急度分 | Must | 支持超期恢复 |
| High-value Goal section protection | 高价值 Goal 的普通优先级任务可进入 pinned | Must | 避免被琐事挤掉 |
| Overdue Goal section protection | 超期 Goal 的下一步任务进入 pinned | Must | 即使 Task 无 deadline |
| Eval v3 scenarios | 新增 2 个固定场景 | Must | 多 Goal / overdue Goal |
| JSONL item signals | 输出 goal value / urgency signal | Should | 支持 compare |

### 用户故事

```text
作为 Chronos 用户，
我希望系统能保护高价值目标的下一步，
以便重要目标不会被看似紧急但价值较低的任务挤掉。
```

```text
作为 Chronos 用户，
我希望目标滞后时 Today 能把下一步拉回前面，
以便我能恢复目标推进，而不是只看到零散任务列表。
```

```text
作为后端开发者，
我希望 planner eval 能覆盖多 Goal 竞争和超期 Goal 恢复，
以便后续调权重、改 prompt 或接真实 provider 时能发现核心编排退化。
```

### 主要流程

```text
collect active tasks
-> eager load related Goal
-> score task value / goal value / task deadline / goal deadline
-> section protection for high-value or overdue goals
-> apply capacity
-> write score_breakdown and eval JSONL item_signals
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
- [x] Scripts
- [x] Docs

### 数据模型变更

无。

`DailyPlanItem.score_breakdown` 增加字段：

```text
goal_value_score
goal_urgency_score
```

### 状态机变更

无。

### 事件变更

无。

### API 变更

无新增接口。Today / Strategy Detail 的已有 `score_breakdown` 会包含新增解释字段。

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [x] 修改 fallback

### Agent 设计

- Agent 名称：Planning Engine v1 / Daily Planner Agent shell
- 输入对象：Task、Goal、TaskDependency、ActivityEvent、UserSettings、EnergyDailyMetric
- 输出对象：DailyPlanItem section / sort_order / recommendation_reason / score_breakdown
- Pydantic schema：不变
- fallback 策略：deterministic Planning Engine 仍是 fallback
- 是否需要用户确认：不需要确认排序；用户可通过 replan / priority adjustment / postpone 修正

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] 高价值 Goal 的关联任务会产生 `goal_value_score`。
- [x] 超期 Goal 的关联任务会产生 `goal_urgency_score`。
- [x] 多 Goal 竞争场景中，高价值 Goal task 排在低价值 Goal task 前。
- [x] 超期 Goal 场景中，无 task deadline 的下一步仍被拉入 pinned。
- [x] `scripts/evaluate_planning_engine.py` 输出 9 个场景且全部通过。
- [x] JSONL 每次输出 1 条 summary 和 9 条 scenario records。

### 数据验收

- [x] 不新增 migration。
- [x] 不写真实用户数据。
- [x] 不调用真实 provider。
- [x] 系统容量滚动仍不改变 Task 本体状态。

### 体验验收

- [x] Today 首屏不新增控制项。
- [x] Strategy Detail 可解释新增 score。
- [x] Goal 复杂度留在后台评分和详情解释层。

---

## 8. 测试计划

### 单元测试

- [x] `tests.test_planning_engine_evaluation`
- [x] `tests.test_today_services`
- [x] `tests.test_planner_eval_compare`

### API 测试

- [ ] 本轮不涉及 API。

### 集成测试

- [x] `scripts/evaluate_planning_engine.py --jsonl-output ...`
- [x] `scripts/verify_local.py --planner-eval --all-smoke`

### 手动验证

```bash
uv run python -m unittest tests.test_planning_engine_evaluation
uv run python -m unittest tests.test_today_services tests.test_planner_eval_compare
uv run python scripts/evaluate_planning_engine.py --run-id goal-aware-v3 --jsonl-output /tmp/chronos-planner-goal-aware-v3.jsonl
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Goal 分数过强 | Goal 下所有任务挤占 Today | 使用轻量加分，并限制 section protection |
| 超期 Goal 过度抢占 | 用户每天都被 overdue 压迫 | 只拉回下一步任务，用户仍可 postpone / replan |
| 评分字段增加 | Strategy Detail 解释变复杂 | Today 首屏不展示完整评分 |

### 关键取舍

- 取舍 1：Goal value / urgency 是轻量加分，不替代 Task 自身 value / deadline。
- 取舍 2：高价值 Goal 只保护普通优先级以上任务，避免所有低优先级任务都 pinned。
- 取舍 3：本轮通过 evaluator 固化行为，不新增 API 字段。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | evaluator version 升级到 v3 | 场景集合和 item signals 变化 | JSONL compare 可识别 |
| 2026-05-17 | 增加 `goal_value_score` | 高价值目标需要进入 Today 编排 | 多 Goal 竞争更贴近产品定位 |
| 2026-05-17 | 增加 `goal_urgency_score` | 超期目标需要恢复推进 | 无 task deadline 也能拉回 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | Goal-aware scoring | `app/services/planning_service.py` | goal value / deadline |
| 2026-05-17 | Eval v3 scenarios | `scripts/evaluate_planning_engine.py` | 9 scenarios |
| 2026-05-17 | Compare item signal fields | `scripts/compare_planner_eval_jsonl.py` | goal signals |
| 2026-05-17 | 更新 tests | `tests/test_planning_engine_evaluation.py` | JSONL 10 records per run |
| 2026-05-17 | 更新文档 | README / LLM / Engineering / Iterations | 当前事实 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_planning_engine_evaluation`
- [x] `uv run python -m unittest tests.test_today_services tests.test_planner_eval_compare`
- [x] `uv run python scripts/evaluate_planning_engine.py --run-id goal-aware-v3 --jsonl-output /tmp/chronos-planner-goal-aware-v3.jsonl`
- [x] `uv run python scripts/verify_local.py --planner-eval --all-smoke`
- [x] `git diff --check`

### 未验证

- [ ] 未用真实 provider 输出做差异对比。
- [ ] 未覆盖真实用户任务分布。

### 已知问题

- Goal-aware scoring 仍是第一版轻量权重，后续需要结合真实执行数据和用户反馈调参。

---

## 13. 后续迭代建议

1. 增加验收记录生成脚本，从 smoke JSON 和 compare JSON 自动生成 Markdown 草稿。
2. 已在后续迭代补充 planner eval golden baseline policy，记录可接受的 changed / regression 标准。
3. 为 Today Strategy Detail 增加更清晰的 goal-aware explanation 文案，但仍不进入 Today 首屏。
