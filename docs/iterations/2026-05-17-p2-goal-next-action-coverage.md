# Iteration: P2 Goal Next Action Coverage

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让 Today 不只是按单个任务排序，还能为每个高价值 / 临近截止目标保护一个最适合今天推进的下一步，避免一个目标的任务堆挤掉另一个重要方向。

---

## 2. 背景与目标

Chronos 的核心是“高价值目标优先完成”。已有 Planning Engine 会读取 Goal 价值和 deadline，但仍可能把一个目标下的多个任务排在前面。本轮补上目标覆盖保护：每个重要目标至少有一个下一步行动进入 Today 主序列。

目标：

- 从 active / postponed tasks 中识别高价值或 7 天内截止目标。
- 为每个目标选择一个未阻塞、未延后、依赖深度更浅、截止更近、优先级更高的 next action。
- 在 `score_breakdown` 中写入 `goal_next_action_score`。
- 在 Strategy Detail 中暴露 `goal_next_action_count` 和解释。

非目标：

- 不做甘特图 / 项目管理。
- 不做复杂多目标资源分配器。
- 不让 LLM 改排序。
- 不扩 P3/P4。

---

## 3. 产品约束对齐

```text
Goals -> Goal next action -> Today main sequence -> Focus
```

- [x] 强化 Goals 与 Today 的主线关系
- [x] 保持 deterministic Planning Engine 为 source of truth
- [x] Strategy Detail 解释，Today 首屏不变复杂
- [x] 不新增 Agent / Prompt / Migration

---

## 4. 需求范围

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Goal next action selection | 为重要目标选一个 next action | Must | 高价值 / 临近截止目标 |
| Goal next action scoring | `goal_next_action_score` 进入 score breakdown | Must | 轻量加分 |
| Goal next action factors | Strategy factors 返回 `goal_next_action_count` | Should | 用于解释 |
| Goal next action rationale | task rationale 暴露 `goal_next_action` signal | Should | 不改变 Today 首屏结构 |

### 用户故事

```text
作为同时推进多个目标的用户，
我希望 Chronos 不只把任务按分数排队，
而是每天帮每个重要目标保留一个能推进的下一步。
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

### 关键字段

- `score_breakdown.goal_next_action_score`
- `factors.goal_next_action_count`
- `score_signals[].key = goal_next_action`

---

## 6. AI / LLM 影响

本轮不新增 LLM 能力。目标下一步保护是 Planning Engine 的确定性规则，用来承接 Goal 系统，不改变 bounded agent 边界。

---

## 7. 验收标准

- [x] 高价值目标会各自选出一个下一步行动。
- [x] next action 排在同目标低优先级后续任务前。
- [x] Strategy Detail 返回 `goal_next_action_count`。
- [x] task rationale 可解释 `goal_next_action`。

---

## 8. 主线偏离 Review

本轮直接补强 `Goals -> Today -> Focus`，没有进入 P3/P4、商业化、前端页面或 provider 验收。它让 Chronos 更接近“每天帮用户推进高价值目标”的核心定义。

---

## 9. 验证记录

```bash
uv run python -m unittest tests.test_today_services
```

结果：27 tests OK。

```bash
uv run python scripts/verify_local.py --planner-eval --planner-eval-policy
```

结果：307 tests OK；compile OK；git diff --check OK；9 个 planner eval 场景通过；planner eval policy 无 regression / change。

```bash
.venv/bin/python3 scripts/verify_local.py --smoke mainline-state
```

结果：307 tests OK；compile OK；git diff --check OK；MAINLINE-STATE smoke passed。
