# Iteration: P2 Minimum Viable Execution Progress

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

补齐“最小推进切片”的执行口径：当 Today 只安排一个高价值大任务的最小推进动作时，用户完成的是当前切片，不应把整个 Task 标记为完成。现在完成切片会让 DailyPlanItem 完成、Task 记录部分进度并保持 active。

---

## 2. 背景与目标

Planning Engine 已经能在时间不够时保护高价值任务的最小推进动作。但如果执行层仍把该动作当作整个任务完成，会破坏 Chronos 的核心承诺：今天做得出来，并持续接近目标。

目标：

- Today 快速完成最小推进切片时，Task 不进入 completed。
- Focus 完成最小推进切片时，Task 不进入 completed。
- Task 记录 `progress` 和实际投入时间，供下一轮编排校准。
- 当前 DailyPlanItem 仍标记 completed，用于今日进度和报告。
- 同日 replan 不把已完成切片重新塞回主序列。
- Daily Report 的完成率可以承认已完成计划切片，但完成任务数只统计真正 completed 的 Task。
- Goal progress 汇总 Task partial progress，让“今天推进了一小步”体现在目标进度上。

非目标：

- 不新增复杂的子状态或控制面板。
- 不做前端页面。
- 不引入 P3/P4 或复杂提醒。
- 不让 LLM 决定完成状态。

---

## 3. 产品约束对齐

```text
Minimum viable slice -> complete slice -> partial Task progress -> next plan continues from remaining work
```

- [x] Today 保持轻量，只展示完成的计划项。
- [x] Task Detail / Goal 后续能看到真实 progress，而不是误完成。
- [x] Focus 不变成控制面板。
- [x] Planning Engine 继续通过执行反馈校准剩余估时。

---

## 4. 需求范围

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Partial task progress | 新增任务部分进度记录能力 | Must | Task 保持 active |
| Today slice completion | Today 完成最小推进项时记录部分进度 | Must | DailyPlanItem completed |
| Focus slice completion | Focus 完成最小推进项时记录部分进度和实际时长 | Must | 计入 focus minutes |
| Same-day replan stability | 同日 replan 保留已完成切片，不重复排同一任务 | Must | 避免进度回退 |
| Activity event | 记录 `TASK_PARTIAL_PROGRESS_RECORDED` | Should | 供报告 / 洞察使用 |
| Report metrics | Daily Report 不把 partial slice 当作 completed task | Should | completion_rate 仍按计划项 |
| Goal progress | Goal completion_rate 汇总 Task progress | Should | completed_task_count 仍只算完成任务 |

### 用户故事

```text
作为用户，
当 Chronos 今天只安排了一个大任务的最小推进动作，
我完成它后希望今天的进度被承认，
但这个大任务本身不要被误标为全部完成。
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [ ] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Reports
- [x] Tests

### 执行规则

判断来源：

```text
DailyPlanItem.score_breakdown.minimum_viable_progress_applied == true
```

完成普通任务：

```text
Task.status = completed
Task.progress = 1.00
DailyPlanItem.status = completed
```

完成最小推进切片：

```text
Task.status = active
Task.progress += planned_duration_min / original_estimated_duration_min
DailyPlanItem.status = completed
ActivityEvent = TASK_PARTIAL_PROGRESS_RECORDED
```

---

## 6. AI / LLM 影响

不新增 Agent，不新增 prompt。LLM 只提供 `minimum_viable_step` 等语义信号；执行状态由后端确定性规则决定。

---

## 7. 验收标准

- [x] Today 完成普通任务仍会完成 Task。
- [x] Today 完成最小推进切片只记录 partial progress。
- [x] Focus 完成最小推进切片只记录 partial progress，并累计 actual duration / focus minutes。
- [x] 同日 replan 保留已完成切片，不把同一 active task 重新排入主序列。
- [x] 产生 `TASK_PARTIAL_PROGRESS_RECORDED`，不产生 `TASK_COMPLETED`。
- [x] Daily Report 的 `completed_task_count` 不统计 partial slice，`completion_rate` 仍可体现计划项完成。
- [x] Goal Detail / Goals Home 的 progress 能反映 Task partial progress。

---

## 8. 主线偏离 Review

本轮直接修正 `Today -> Task Detail -> Focus -> Report` 的状态语义，是核心闭环问题。没有扩展 P3/P4、商业化、前端、auth 或 provider acceptance。

---

## 9. 验证记录

```bash
uv run python -m unittest tests.test_today_services tests.test_focus_services
```

结果：36 tests OK。

```bash
uv run python -m unittest tests.test_report_me_services tests.test_today_services tests.test_focus_services
```

结果：45 tests OK。

```bash
uv run python -m unittest tests.test_task_goal_services tests.test_task_goal_api tests.test_report_me_services tests.test_today_services tests.test_focus_services
```

结果：90 tests OK。

```bash
uv run python scripts/verify_local.py --planner-eval --planner-eval-policy
```

结果：314 tests OK；compile OK；git diff --check OK；9 个 planner eval 场景通过；planner eval policy 无 regression / change。

```bash
.venv/bin/python3 scripts/verify_local.py --smoke mainline-state
```

结果：314 tests OK；compile OK；git diff --check OK；MAINLINE-STATE smoke passed。
