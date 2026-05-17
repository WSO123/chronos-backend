# Iteration: P2 Today AI Signal Preparation

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让 Today 拥有一个受控入口，为当前主序列任务生成缺失的 TaskPlanningSignal，并在有新信号后重新编排，让 AI 语义理解真正进入每日计划。

---

## 2. 背景与目标

Task Semantic Planning Agent 已经能生成语义信号，Planning Engine 也已经能消费这些信号。但如果只能在 Task Detail 手动逐个触发，Today 的智能编排仍然不够顺。本轮补一个 Today 级准备入口。

目标：

- `POST /api/v1/today/planning-signals` 读取当前 Today 的 pinned / recommended / low priority tasks。
- 对缺失 TaskPlanningSignal 的任务生成 bounded semantic signal。
- 如果生成了新 signal，触发 deterministic replan。
- 返回生成数量、已有数量、AIJob ids、Signal ids 和刷新后的 Today。

非目标：

- 不在 `GET /today` 首屏自动调用 provider。
- 不让 LLM 直接改排序。
- 不对所有历史任务批量跑 AI。
- 不扩 P3/P4。

---

## 3. 产品约束对齐

```text
Today -> prepare AI signals -> deterministic replan -> Focus
```

- [x] AI 帮助编排，但不接管 source of truth
- [x] 操作受控、可追踪、可解释
- [x] Today 首屏不变成复杂驾驶舱
- [x] 不绕过用户的 Task / Goal 状态

---

## 4. 需求范围

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Today signal preparation API | 为 Today 主序列生成缺失 TaskPlanningSignal | Must | `limit` 默认 10 |
| Existing signal skip | 已有 signal 的任务不重复生成 | Must | 控制成本 |
| Deterministic replan | 有新 signal 后才 replan | Must | Planning Engine 仍是排序源 |
| Response contract | 返回 ids、counts、updated today | Should | 前端可直接刷新 |

### 用户故事

```text
作为用户，
我希望 Today 可以主动准备 AI 语义理解，
让系统更懂每个任务对目标的价值，
但我不希望 AI 在背后静默乱改计划。
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [ ] Models
- [x] Schemas
- [ ] Workers
- [x] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### API

```http
POST /api/v1/today/planning-signals?plan_date=2026-05-16&limit=10&replan=true
```

返回：

- `task_count`
- `generated_count`
- `existing_count`
- `skipped_count`
- `replanned`
- `planning_signal_ids`
- `ai_job_ids`
- `today`

---

## 6. AI / LLM 影响

本轮复用 Task Semantic Planning Agent，不新增 prompt。Agent 只写 TaskPlanningSignal 和 AIJob trace；排序仍由 Planning Engine 使用 signal 后重新计算。

---

## 7. 验收标准

- [x] Today 可为缺失 signal 的任务生成 TaskPlanningSignal。
- [x] 已有 signal 不重复生成。
- [x] 有新 signal 时 Today version 增加。
- [x] 新 Today item 的 `score_breakdown.semantic_signal_applied=true`。
- [x] API 返回 AIJob / signal ids。

---

## 8. 主线偏离 Review

本轮没有做自动化 provider 接入、P3/P4 或前端页面。它补的是 AI 语义信号进入 Today 编排的受控入口，符合“AI 编排但可解释、可追踪、不黑箱改状态”的主线。

---

## 9. 验证记录

```bash
uv run python -m unittest tests.test_today_api tests.test_today_services
```

结果：33 tests OK。

```bash
uv run python scripts/verify_local.py --planner-eval --planner-eval-policy
```

结果：308 tests OK；compile OK；git diff --check OK；9 个 planner eval 场景通过；planner eval policy 无 regression / change。

```bash
.venv/bin/python3 scripts/verify_local.py --smoke mainline-state
```

结果：308 tests OK；compile OK；git diff --check OK；MAINLINE-STATE smoke passed。
