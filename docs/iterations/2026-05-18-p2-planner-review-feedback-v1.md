# Iteration: P2 Planner Review Feedback v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 关联 Commit：待提交

---

## 1. 迭代摘要

给 Strategy Detail 的 Planner Review 增加轻量用户反馈：用户可以接受或忽略一条 AI 建议，系统用 ActivityEvent 留痕，并把最近反馈作为后续 Daily Planner Agent 的只读上下文。

---

## 2. 背景与目标

Chronos 的长期价值不是一次性建议，而是逐步理解用户的执行偏好。但当前 Planner Review 只会给出建议，无法知道用户是否认同这些建议。为了避免把 LLM 做成隐藏控制面，本轮只记录反馈并影响后续审阅语气和建议，不直接改变排序或任务状态。

### 目标

- 新增 `POST /api/v1/today/planner-review/feedback`。
- 反馈写入 `PLANNER_REVIEW_FEEDBACK_RECORDED` ActivityEvent。
- 反馈结果明确 `applied_to_plan=false`、`replan_triggered=false`。
- 后续 Daily Planner Agent 读取只读 `user_feedback` context。
- mock review 能根据最近忽略的 `respect_rollover` 改成更贴近用户的手动容量建议。

### 非目标

- 不让 LLM 直接修改 Today 排序。
- 不自动 replan。
- 不新增画像表或复杂偏好系统。
- 不做 P3/P4、前端页面、商业化或提醒。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Planner Review Feedback -> 下一次 Strategy Detail
```

本轮服务的是“Chronos 越来越懂用户”的 P2 智能解释层，而不是新增一个控制台。

### 用户故事

```text
作为一个每天时间状态不同的用户，
我希望可以告诉 Chronos 哪些 AI 建议对我有用、哪些不适合我，
以便后续审阅能更贴近我的真实执行偏好。
```

```text
作为 Planning Engine，
我希望用户反馈先作为只读上下文进入 Daily Planner Agent，
以便保留 deterministic order 的可信边界。
```

### 设计护栏

- [x] 不让 Today 变成复杂驾驶舱。
- [x] 不让 Task Detail 变成信息仓库。
- [x] 不让 Focus 变成控制面板。
- [x] 不让解释抢走行动感。
- [x] 不让“聪明”压过“可信”。

---

## 4. 需求范围

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Feedback API | 记录 planner suggestion 的 accepted / ignored | Must | 当前 Strategy Detail suggestion key |
| ActivityEvent | 写入 `PLANNER_REVIEW_FEEDBACK_RECORDED` | Must | 不新增 DB 表 |
| Review context | Daily Planner Agent 读取近期反馈摘要 | Must | 只读 |
| Mock adaptation | 被忽略的 rollover 建议改成手动容量建议 | Should | 本地可验证 |

### 主要流程

```text
GET /today/strategy
-> 用户看到 planner_review.suggestions[]
-> POST /today/planner-review/feedback
-> ActivityEvent 记录反馈
-> 下一次 replan / Strategy Detail
-> Daily Planner Agent 读取 user_feedback context
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

### 数据模型变更

无。使用现有 `ActivityEvent.payload`。

### 事件变更

新增事件：

```text
PLANNER_REVIEW_FEEDBACK_RECORDED
```

Payload 核心字段：

```json
{
  "suggestion_key": "respect_rollover",
  "action": "ignored",
  "learning_signal": "planner_review_preference",
  "applied_to_plan": false,
  "replan_triggered": false
}
```

---

## 6. 验收标准

- [x] 只有当前 Planner Review 中存在的 suggestion key 可被反馈。
- [x] 反馈不会创建 Today，也不会自动 replan。
- [x] 反馈写入 ActivityEvent。
- [x] Daily Planner Agent 的 `review_context.user_feedback` 能读到 recent / accepted / ignored 摘要。
- [x] 被忽略的 `respect_rollover` 会让后续 mock review 改成 `adjust_capacity_if_needed`。

---

## 7. 测试计划

```bash
uv run python -m unittest tests.test_daily_planner_agent tests.test_today_services tests.test_today_api
.venv/bin/python -m compileall app tests scripts
uv run python -m unittest discover -s tests
uv run python scripts/verify_local.py --planner-eval --planner-eval-policy
git diff --check
```

---

## 8. 防偏航 Review

- 本轮只增强 P2 Strategy Detail / bounded AI Agent 主线。
- 没有新增 P3/P4 或商业化。
- 没有新增重型用户画像系统。
- 没有让反馈立刻改变任务状态。
- 没有让 LLM 直接接管排序。

---

## 9. 下一轮建议

P2 Planner Feedback Scoring Signal v1：把用户反复接受 / 忽略的反馈压缩成确定性小权重，例如用户持续忽略 rollover 建议时只在 Strategy Detail 暴露“容量边界偏好”，暂不直接扩大 Today 容量。
