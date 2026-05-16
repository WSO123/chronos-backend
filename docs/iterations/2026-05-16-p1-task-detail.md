# Iteration: P1 Task Detail

> 状态：Done
> 阶段：P1
> 创建日期：2026-05-16
> 负责人：Chronos Team
> 关联 PR / Issue / Commit：

---

## 1. 迭代摘要

将 `GET /api/v1/tasks/{task_id}` 从基础 Task 资源读取升级为 Task Detail 轻量聚合接口，为 Today / Goals 到 Focus 的中间承接层提供执行前必要信息。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

Today 已经能输出推荐执行顺序，Focus 已经能记录执行行为。Task Detail 是从 AI 决策走向执行的过渡层，需要展示任务基本信息、所属 Goal、轻量建议、步骤、当前 Today 上下文和可执行动作，但不能成为信息仓库。

### 目标

- 保持 `GET /api/v1/tasks/{task_id}` 作为 Task Detail 入口。
- 返回任务基础字段和步骤。
- 返回轻量 Goal 摘要。
- 返回 P1 规则版执行建议。
- 返回当前 Today item 上下文。
- 返回当前 Focus 状态和下一步 actions。
- 不默认返回历史事件。

### 非目标

- 不实现任务历史聚合，历史继续通过 `/tasks/{task_id}/events` 获取。
- 不实现 P2 任务依赖。
- 不实现 P3 来源上下文聚合。
- 不接真实 LLM task breakdown。
- 不改变 Task / Goal / Focus 的状态机。

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

Task Detail 只帮助用户进入下一步行动，不展示复杂历史、来源仓库或策略解释。AI 信息是规则版轻量建议，而不是长篇分析。

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
| Task Detail Response | 聚合执行前必要信息 | Must | 复用 `/tasks/{id}` |
| Goal Summary | 返回轻量 Goal 信息 | Must | 不做完整 Goal Detail |
| AI Info | 返回推荐时长、优先级、执行建议 | Must | P1 规则生成 |
| Today Context | 返回当前 Today item 上下文 | Must | 若任务不在 Today 则为空 |
| Focus State | 返回 active focus 信息 | Must | 用于禁用重复 Start Focus |
| Actions | 返回可执行动作开关 | Must | 前端据此展示按钮 |

### 用户故事

```text
作为 Chronos 用户，
我希望从 Today 进入任务详情时，
能快速确认任务、步骤、建议和下一步动作，
然后顺滑进入 Focus。
```

### 主要流程

```text
GET /tasks/{id}
-> Task + Steps
-> Goal Summary
-> Today Context
-> Focus State
-> Actions
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

无。Task Detail 是读取聚合，不写入 ActivityEvent。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/tasks/{task_id}` | Task Detail 轻量聚合 | path task id | TaskDetailResponse |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及 mock/rule Agent
- [ ] 新增真实 Agent
- [ ] 修改真实 LLM Prompt
- [ ] 修改 Structured Output
- [x] 修改 fallback

### Agent 设计

P1 不接真实 LLM。`TaskService.get_task_detail` 根据任务状态、步骤、优先级和价值等级生成轻量 `execution_suggestion`。

### LLM 安全边界

- [x] Task Detail 不调用真实 LLM。
- [x] 规则建议不改变任务状态。
- [x] 复杂拆解和 AI breakdown 延后到后续迭代。

---

## 7. 验收标准

### 功能验收

- [x] `GET /tasks/{id}` 返回 Task Detail 聚合。
- [x] 返回任务基础字段和步骤。
- [x] 返回轻量 Goal 摘要。
- [x] 返回轻量执行建议。
- [x] 返回当前 Today item 上下文。
- [x] 返回当前 Focus 状态。
- [x] 返回 actions：start focus / complete / postpone / edit。
- [x] 不同 `X-User-Id` 之间数据隔离。

### 数据验收

- [x] 不新增表。
- [x] 不写入 ActivityEvent。
- [x] 不返回任务历史事件。
- [x] steps 按 `sort_order` 稳定返回。

### 体验验收

- [x] Task Detail response 不包含历史事件列表。
- [x] Task Detail response 不包含复杂来源上下文。
- [x] Task Detail response 不包含 P2 依赖图。

---

## 8. 测试计划

### 单元测试

- [x] Task Detail 返回 Goal / AI Info / Today Context / Actions。
- [x] active Focus 存在时，其他任务的 `can_start_focus=false`。

### API 测试

- [x] `GET /tasks/{id}` 返回 Task Detail 聚合。
- [x] user isolation 沿用原测试覆盖。

---

## 9. 验证记录

- [x] `.venv/bin/python -m unittest discover -s tests`
- [x] `.venv/bin/python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 10. 风险与后续

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| P1 执行建议较简单 | 智能感有限 | 后续接 Task Breakdown Agent |
| Today Context 只取用户当天 active plan | 暂不支持查看历史 / 未来 plan detail | P1 先服务当前执行闭环 |
| 不返回来源上下文 | P3 来源关联暂不可见 | 后续 Related Context 单独扩展 |

---

## 11. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-16 | `GET /tasks/{id}` 作为 Task Detail 聚合入口 | 与架构文档一致，减少新端点 | 旧基础字段保持兼容 |
| 2026-05-16 | 历史事件仍走 `/events` | 防止 Task Detail 变成信息仓库 | 前端按需加载历史 |
| 2026-05-16 | P1 使用规则建议 | 不让真实 LLM 阻塞闭环 | 后续可替换 Agent |

---

## 12. 文件变更

| 日期 | 变更 | 文件 | 说明 |
| --- | --- | --- | --- |
| 2026-05-16 | 新增 Task Detail schema | `app/schemas/tasks.py` | TaskDetailResponse |
| 2026-05-16 | 新增 Task Detail service 聚合 | `app/services/task_service.py` | Goal / Today / Focus / Actions |
| 2026-05-16 | 调整 GET task response model | `app/api/v1/tasks.py` | 仍使用 `/tasks/{id}` |
| 2026-05-16 | 新增测试 | `tests/test_task_goal_services.py`、`tests/test_task_goal_api.py` | 回归覆盖 |

---

## 13. 下一步

- review 本迭代需求和代码。
- 如无优化项，进入下一轮：AIJob 查询接口或 Task Breakdown rule/mock。
