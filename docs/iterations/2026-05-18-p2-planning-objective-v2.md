# Iteration: P2 Planning Objective v2

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

把 Today 编排从“任务打分后按顺序装入容量”，升级为“在今日可用时间内最大化高价值目标推进”的确定性选择逻辑。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

Chronos 的核心不是更聪明的任务列表，而是帮用户把今天安排成真正做得出来的一天。前序迭代已经完成 Goal Progress Feedback、手动可用时间和语义/执行学习信号，但容量选择仍偏“按排序顺序填充”。这会让 Today 在某些短容量场景下优先选择普通任务，而不是对高价值目标更有推进意义的后续动作。

### 目标

- 让 Planning Engine 在非保护任务里按 objective 选择今日主序列。
- objective 明确偏向高价值 Goal、目标下一步、目标进度压力、语义目标对齐和最小推进动作。
- 在 Strategy Detail 暴露 objective 版本、收益分和解释信号，保持可解释与可校正。

### 非目标

- 不新增 DB 表。
- 不新增 Agent，不让 LLM 接管排序。
- 不做 P3/P4、商业化、前端页面或外部集成。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
Goals -> Goal Detail -> Task Detail -> Focus
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [x] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

本轮把复杂选择留在 Planning Engine 背后，用户看到的是更可信的 Today 主序列和 Strategy Detail 中克制的解释。Today 不增加复杂控制项，只让“今天先做什么”更贴近高价值目标推进。

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
| Planning Objective Score | 为每个候选任务计算容量目标收益分 | Must | 不替代原 total_score，而是用于容量选择 |
| Capacity Objective Selection | 非保护任务用确定性 0/1 选择逻辑进入剩余容量 | Must | 保护任务仍保留既有高价值/紧急保护 |
| Strategy Detail Objective Factors | 暴露 objective 版本、选中收益、滚动收益、高价值目标选中数 | Must | 用于解释和回归评估 |
| Planner Eval Scenario | 增加短容量下保护高价值目标推进的离线场景 | Must | 升级 baseline 到 v8 |

### 用户故事

```text
作为高自驱但时间有限的用户，
我希望 Chronos 在今天时间不够时优先安排真正推进高价值目标的任务，
以便我不是完成更多杂事，而是每天更接近重要目标。
```

```text
作为 Planning Engine，
我希望在容量约束下选择 objective 收益最高的任务组合，
以便 Today 的主序列符合 AI Execution OS 的核心承诺。
```

### 主要流程

```text
读取任务、Goal、语义信号、执行反馈和今日可用时间
-> 计算原有 score_breakdown
-> 为候选任务计算 planning objective
-> 保护 pinned 任务
-> 在剩余容量内选择 objective 收益最高的非保护任务组合
-> 其余任务滚动到未来
-> Strategy Detail 暴露解释和回归信号
```

---

## 5. 后端设计

### 影响模块

- [ ] API
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

无新增事件。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/today/strategy` | Strategy Detail 读取 objective factors | 无 | 新增 objective 字段 |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

不新增 Agent。Daily Planner Agent 仍只能审阅 deterministic Planning Engine 结果，不能重排、移区或写任务状态。

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] 今日剩余容量不足以容纳所有任务时，普通任务可被滚动，高价值目标后续动作可进入主序列。
- [x] `score_breakdown` 暴露 `planning_objective_score`、`planning_objective_selected` 和 reason key。
- [x] Strategy Detail 暴露 objective 版本和收益统计。

### 数据验收

- [x] 不新增持久化模型。
- [x] DailyPlanItem section / status 仍按既有规则落库。
- [x] Planner eval policy 能检查 objective 字段。

### 体验验收

- [x] Today 不新增复杂解释入口。
- [x] Strategy Detail 能解释为什么普通任务滚动、高价值目标动作被保留。
- [x] AI Agent 失败不影响确定性编排。

---

## 8. 测试计划

### 单元测试

- [x] `test_planning_objective_uses_remaining_capacity_for_high_value_goal_progress`
- [x] 容量滚动、手动可用时间、policy version 聚焦回归

### API 测试

- [ ] 本轮未新增 API path。

### 集成测试

- [x] `scripts/evaluate_planning_engine.py` v8
- [x] `scripts/check_planner_eval_policy.py`

### 手动验证

```text
1. 创建高价值 Goal 的第一步和后续动作。
2. 设置今日可用时间为 90 分钟。
3. 验证 first step + goal followup 进入主序列，普通 admin task 滚动到未来。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| objective 权重过强 | 可能让低优先级但关联高价值 Goal 的任务进入主序列 | 仅作用于容量选择，仍保留 pinned 保护、用户手动可用时间和 Strategy Detail 解释 |
| 选择逻辑更复杂 | 后续调参风险增加 | 用 planner eval v8 和 score_breakdown 字段固定可解释契约 |

### 关键取舍

- 取舍 1：使用确定性 objective 选择，不让 LLM 直接排序。
- 取舍 2：不新增表，把 objective 作为 score_breakdown / Strategy Detail 派生字段。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-18 | objective 只选择非保护任务 | pinned 仍代表高价值、截止、依赖等硬保护 | 避免破坏 P1/P2 已稳定主线 |
| 2026-05-18 | planner eval 升级到 v8 | 需要把“容量内保护 Goal 推进”纳入长期回归 | policy required scenario count 从 12 到 13 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-18 | 新增 planning objective 和容量选择 | `app/services/planning_service.py` | 确定性 objective，不新增 Agent |
| 2026-05-18 | 扩展 Strategy Detail factors schema | `app/schemas/today.py` | 暴露 objective 可解释字段 |
| 2026-05-18 | 增加单测与 planner eval v8 | `tests/`, `scripts/`, `docs/planner-eval-baselines/` | 13 个场景 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_today_services.TodayServiceTests.test_planning_objective_uses_remaining_capacity_for_high_value_goal_progress tests.test_today_services.TodayServiceTests.test_planning_engine_rolls_over_work_beyond_today_capacity tests.test_today_services.TodayServiceTests.test_replan_uses_manual_available_minutes_and_preserves_it tests.test_planner_eval_policy.PlannerEvalPolicyTests.test_bundled_policy_matches_current_evaluator_version`
- [x] `uv run python scripts/evaluate_planning_engine.py --run-id p2-objective-v2 --jsonl-output /tmp/chronos-planner-objective-v2.jsonl`
- [x] `uv run python scripts/check_planner_eval_policy.py /tmp/chronos-planner-objective-v2.jsonl`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

### 未验证

- [ ] 无。

### 已知问题

- 暂无。

---

## 13. 后续迭代建议

- P2 Semantic Planning Coverage v2：让 LLM 语义信号更明确输出目标相关性、最小推进动作、复杂度和估时置信度，继续作为 Planning Engine 输入。
- P2 Execution Learning v2：用 Focus/Report 结果校准 objective 权重和估时，但必须保持可解释与用户可修正。
- P2 Goal Progress Feedback v2：把 objective 选择结果更清晰地回流到 Goal Detail 的推荐下一步。
