# Iteration: P2 Task Planning Signal Freshness

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让 TaskPlanningSignal 具备轻量新鲜度判断。任务、目标、步骤、依赖或执行进度发生变化后，旧语义信号不再被 Planning Engine 继续消费；Today 的受控准备入口会刷新过期信号并重新编排。

---

## 2. 背景与目标

上一轮已经让 Today 可以生成缺失 TaskPlanningSignal，并让 Planning Engine 使用语义估时、目标对齐、认知负荷和最小推进动作。但如果任务内容修改后旧 signal 仍被继续使用，系统会出现“AI 理解停留在旧任务”的问题。

目标：

- TaskPlanningSignal 生成时记录输入签名。
- Planning Engine 只消费仍然新鲜的 TaskPlanningSignal。
- `POST /api/v1/today/planning-signals` 能识别并刷新过期 signal。
- Response 暴露 `stale_count`，方便前端或调试知道本次刷新原因。

非目标：

- 不做后台自动批量刷新。
- 不在 `GET /today` 首屏静默调用 provider。
- 不让 LLM 直接改排序。
- 不扩 P3/P4 或 provider acceptance。

---

## 3. 产品约束对齐

```text
Task / Goal context changed -> signal becomes stale -> controlled refresh -> deterministic replan
```

- [x] AI 语义理解可以更新，但仍由用户触发的受控入口进入 Today。
- [x] Planning Engine 仍是排序 source of truth。
- [x] 不让旧 AI 判断悄悄影响新的每日编排。
- [x] Today 首屏保持轻，不新增驾驶舱式信息。

---

## 4. 需求范围

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Input signature | signal 生成时记录任务上下文签名 | Must | 不新增 DB 字段 |
| Freshness check | 判断 signal 是否仍匹配当前上下文 | Must | 覆盖 Task / Goal / steps / dependencies / progress |
| Planner filter | Planning Engine 只读取 fresh signal | Must | 旧 signal 不参与评分 |
| Today refresh | Today preparation 刷新 stale signal | Must | 有刷新才 replan |
| Response contract | 返回 `stale_count` | Should | 保持解释轻量 |

### 用户故事

```text
作为用户，
当我修改任务内容或目标上下文后，
我希望 Chronos 不要继续沿用旧的 AI 理解，
而是在我准备 Today 语义信号时刷新它，
让每日编排真正基于当前任务。
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

### Freshness 规则

优先使用 `TaskPlanningSignal.raw_payload._input_signature`：

```text
current task context signature == stored signature -> fresh
current task context signature != stored signature -> stale
```

对历史 signal 没有签名的情况，使用 `created_at >= context_updated_at` 的时间戳兜底。

输入上下文包含：

- Task 标题、描述、估时、实际投入、优先级、价值等级、deadline、状态、进度
- Goal 标题、描述、deadline、价值等级、状态
- 未完成步骤摘要
- 依赖数量

---

## 6. AI / LLM 影响

不新增 prompt，不改变 provider 调用方式。Task Semantic Planning Agent 仍只生成 TaskPlanningSignal；Planning Engine 决定是否消费 fresh signal。

---

## 7. 验收标准

- [x] 任务未变时，Today preparation 识别 existing signal，不重复生成。
- [x] 任务变更后，Today preparation 识别 stale signal 并刷新。
- [x] stale signal 不被 Planning Engine 消费。
- [x] 刷新 stale signal 后 deterministic replan。
- [x] API 返回 `stale_count`。

---

## 8. 主线偏离 Review

本轮没有做 P3/P4、前端、高级 Auth、商业化或 provider acceptance。它补的是 AI 语义信号的生命周期，直接服务 Today 编排可信度和“系统越来越懂用户当前任务”的主线。

---

## 9. 验证记录

```bash
uv run python -m unittest tests.test_today_api tests.test_today_services tests.test_task_goal_services
```

结果：57 tests OK。

```bash
uv run python scripts/verify_local.py --planner-eval --planner-eval-policy
```

结果：310 tests OK；compile OK；git diff --check OK；9 个 planner eval 场景通过；planner eval policy 无 regression / change。

```bash
.venv/bin/python3 scripts/verify_local.py --smoke mainline-state
```

结果：310 tests OK；compile OK；git diff --check OK；MAINLINE-STATE smoke passed。
