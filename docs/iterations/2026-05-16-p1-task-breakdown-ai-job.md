# Iteration: P1 Task Breakdown / AIJob Query

> 状态：Done
> 阶段：P1
> 创建日期：2026-05-16
> 负责人：Chronos Team
> 关联 PR / Issue / Commit：

---

## 1. 迭代摘要

实现 P1 的任务拆解 rule/mock 能力和 AIJob 查询骨架。用户可以对任务触发 `breakdown`，系统同步生成可编辑步骤，并用 `AIJob` 记录这次 AI / fallback 行为，前端可以通过 AIJob 查询入口查看状态。

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

Task Detail 已经能展示步骤和轻量执行建议。下一步需要补齐“拆解”能力，让用户可以把一个任务变成可执行步骤。P1 不接真实 LLM，但必须保留 AIJob 状态口径，为后续真实 Task Breakdown Agent 接入做准备。

### 目标

- 新增 `POST /api/v1/tasks/{task_id}/breakdown`。
- P1 使用 rule/mock 同步生成 TaskStep。
- 不覆盖已有步骤。
- 已完成 / 归档任务不可拆解。
- 写入 `AIJob`，状态为 `succeeded_with_fallback`。
- 写入 `TASK_BREAKDOWN_GENERATED` 和 `TASK_STEP_CREATED` 事件。
- 新增 `GET /api/v1/ai-jobs/{job_id}` 查询骨架。

### 非目标

- 不接真实 LLM。
- 不实现异步 worker breakdown。
- 不实现用户确认后再写入步骤。
- 不实现步骤编辑 / 删除。
- 不实现 AIJob 列表、取消和重试 API。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [x] Capture
- [x] Inbox
- [x] Today
- [x] Task Detail
- [x] Focus
- [x] Report
- [x] Me
- [x] Goals
- [x] AI Agent

### 产品人格

Task Breakdown 只把任务拆成少量清晰步骤，不生成复杂计划、不覆盖用户已有结构、不制造额外压力。

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
| Task Breakdown API | 对任务生成步骤 | Must | P1 rule/mock |
| AIJob 记录 | 记录拆解行为和 fallback 状态 | Must | 为真实 Agent 预留 |
| AIJob 查询 API | 通过 job id 查询状态 | Must | P1 只做详情 |
| Existing Steps Guard | 已有步骤时不覆盖 | Must | 返回空 created_steps |
| Task Status Guard | 只允许 active / postponed / in_focus 任务拆解 | Must | 完成后不可再生成步骤 |
| ActivityEvent | 记录 breakdown 和 step created | Must | 服务后续行为学习 |

### 用户故事

```text
作为 Chronos 用户，
我希望在 Task Detail 中把任务拆成少量可执行步骤，
以便更容易进入 Focus。
```

### 主要流程

```text
POST /tasks/{id}/breakdown
-> create AIJob(task_breakdown)
-> rule/mock generate steps
-> create TaskStep
-> mark AIJob succeeded_with_fallback
-> return ai_job + created_steps

GET /ai-jobs/{id}
-> return current job status
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

无。复用：

```text
AIJob
TaskStep
ActivityEvent
```

### 状态机变更

P1 同步 rule/mock：

```text
AIJob.queued -> running -> succeeded_with_fallback
```

### 事件变更

- TASK_BREAKDOWN_GENERATED
- TASK_STEP_CREATED

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/tasks/{task_id}/breakdown` | 规则拆解任务步骤 | path task id | TaskBreakdownResponse |
| GET | `/api/v1/ai-jobs/{job_id}` | 查询 AIJob 状态 | path job id | AIJobResponse |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及 mock/rule Agent
- [ ] 新增真实 Agent
- [ ] 修改真实 LLM Prompt
- [x] 修改 Structured Output
- [x] 修改 fallback

### Agent 设计

P1 不接真实 LLM。规则：

- 任务无步骤：按估时生成 3-4 个步骤。
- 任务已有步骤：不覆盖、不追加，返回 `created_steps=[]`。
- AIJob 标记为 `succeeded_with_fallback`，metadata 记录 fallback reason。

### LLM 安全边界

- [x] LLM / rule 不覆盖已有步骤。
- [x] 输出必须落到 TaskStep，可编辑。
- [x] 失败或保守场景不会阻塞 Task Detail / Focus 主链路。

---

## 7. 验收标准

### 功能验收

- [x] 可以触发 task breakdown。
- [x] 无步骤任务会生成步骤。
- [x] 已有步骤任务不会被覆盖。
- [x] 已完成任务不可再拆解。
- [x] 返回 AIJob 信息和 created_steps。
- [x] 可以通过 `GET /ai-jobs/{job_id}` 查询 job。
- [x] 不同 `X-User-Id` 之间数据隔离。

### 数据验收

- [x] AIJob 正确落库。
- [x] AIJob metadata 记录 fallback reason 和 created step ids。
- [x] TaskStep 正确落库。
- [x] 关键动作写入 ActivityEvent。

### 体验验收

- [x] 一次 breakdown 只生成少量步骤。
- [x] 不生成复杂执行计划。
- [x] 不覆盖用户已有步骤。

---

## 8. 测试计划

### 单元测试

- [x] breakdown 创建 rule steps 和 AIJob。
- [x] 已有步骤时不覆盖。

### API 测试

- [x] `POST /tasks/{id}/breakdown`
- [x] `GET /ai-jobs/{job_id}`
- [x] AIJob user isolation

---

## 9. 验证记录

- [x] `.venv/bin/python -m unittest discover -s tests`
- [x] `.venv/bin/python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 10. 风险与后续

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| rule/mock 步骤较通用 | 智能感有限 | 后续接真实 Task Breakdown Agent |
| P1 同步执行 | 不反映真实异步队列 | AIJob schema 已保留 celery_task_id / status |
| 已有步骤时不追加 | 用户可能仍想继续拆 | 后续提供“建议草稿 / 用户确认”模式 |

---

## 11. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-16 | P1 breakdown 同步 rule/mock | 不让真实 LLM 阻塞闭环 | 后续可替换 worker/Agent |
| 2026-05-16 | 已有步骤不覆盖不追加 | 保护用户控制感 | 避免重复步骤 |
| 2026-05-16 | AIJob 查询先做详情 | P1 前端只需知道单个任务状态 | 列表/重试后续补 |

---

## 12. 文件变更

| 日期 | 变更 | 文件 | 说明 |
| --- | --- | --- | --- |
| 2026-05-16 | 新增 AIJob 查询 API / schema | `app/api/v1/ai_jobs.py`、`app/schemas/ai_jobs.py` | 查询 job 状态 |
| 2026-05-16 | 新增 Task Breakdown API / schema | `app/api/v1/tasks.py`、`app/schemas/tasks.py` | breakdown response |
| 2026-05-16 | 新增 breakdown service 逻辑 | `app/services/task_service.py`、`app/services/ai_job_service.py` | rule/mock |
| 2026-05-16 | 新增测试 | `tests/test_task_goal_services.py`、`tests/test_task_goal_api.py` | 回归覆盖 |

---

## 13. 下一步

- review 本迭代需求和代码。
- 如无优化项，进入下一轮：AIJob 状态列表 / retry，或 P1 开发体验与 seed 数据脚本。
