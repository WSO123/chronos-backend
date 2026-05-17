# Iteration: P2 Goal Next Task Dependency Aware

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让 Goals Home 和 Goal Detail 的 recommended next task 避开仍有未完成前置任务的后续任务，保证 `Goals -> Task Detail -> Focus` 路径不会把用户带到暂时不能执行的任务。

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

P2 的 Goal Detail 承载目标推进和下一步推荐。此前 recommended next task 只读取排序最高的未完成任务；如果一个高价值后续任务依赖低优先级前置任务，系统可能推荐后续任务，破坏“真正做得出来”的产品承诺。

### 目标

- Goals Home 的 `recommended_next_task_id` 避开被未完成前置任务阻塞的后续任务。
- Goal Detail 的 `task_list.recommended_next_task` 使用同一逻辑。
- 前置任务完成后，推荐自然切换到后续任务。

### 非目标

- 不做复杂依赖图 UI。
- 不做跨目标路径规划。
- 不引入 LLM。
- 不做 P3/P4 协作。

---

## 3. 产品约束对齐

### 核心路径

```text
Goals -> Goal Detail -> Task Detail -> Focus
```

- [ ] Capture
- [ ] Inbox
- [ ] Today
- [x] Task Detail
- [x] Focus
- [ ] Report
- [ ] Me
- [x] Goals
- [ ] AI Agent

### 产品人格

- 轻盈：仍只给一个 recommended next task。
- 克制：Dependency Map 保持二级信息，不压到 Goals 首页。
- 可信赖：推荐的是能开始做的下一步，而不是被依赖挡住的任务。
- 有判断：当所有任务都被阻塞时，回退到排序最高的未完成任务。

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
| Dependency-aware recommended next task | Goal 推荐下一步避开被阻塞任务 | Must | Goals Home / Detail 共用 |
| Completion handoff | 前置任务完成后推荐后续任务 | Must | 主线可执行 |
| Contract update | 文档说明推荐规则 | Should | 前端联调 |

### 用户故事

```text
作为从 Goal 推进任务的用户，
我希望系统推荐的下一步是现在真的能开始的任务，
以便目标推进不会被隐藏依赖卡住。
```

```text
作为前端开发者，
我希望 Goals Home 和 Goal Detail 使用一致的 recommended next task 规则，
以便两个入口不会给出矛盾建议。
```

### 主要流程

```text
创建 Goal
-> 创建 prerequisite task 和 dependent task
-> 添加 dependent 依赖 prerequisite
-> GET /goals/home 推荐 prerequisite
-> GET /goals/{id}/detail 推荐 prerequisite
-> 完成 prerequisite
-> Goal Detail 推荐 dependent
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
- [x] Tests

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

无新增事件。

### API 变更

无字段变更。既有字段语义增强：

| Method | Path | 字段 | 变化 |
| --- | --- | --- | --- |
| GET | `/api/v1/goals/home` | `recommended_next_task_id` | 避开被未完成前置任务阻塞的任务 |
| GET | `/api/v1/goals/{goal_id}/detail` | `task_list.recommended_next_task` | 与 Goals Home 使用同一规则 |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [x] 不涉及
- [ ] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] 后续任务依赖未完成前置任务时，Goal 推荐前置任务。
- [x] Goals Home 和 Goal Detail 推荐一致。
- [x] 前置任务完成后，Goal Detail 推荐后续任务。

### 数据验收

- [x] 不新增表和迁移。
- [x] 依赖边仍由 `TaskDependency` 提供事实来源。

### 体验验收

- [x] Goals 首页仍只展示轻量 next task id。
- [x] Goal Detail 不变成复杂项目管理面板。

---

## 8. 测试计划

### 单元 / API 测试

- [x] `tests.test_task_goal_services`
- [x] `tests.test_task_goal_api`

### Smoke

- [x] `scripts/verify_local.py --smoke p1-bearer-capture`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 所有未完成任务都被阻塞 | 无法给出严格可执行任务 | 回退到排序最高的未完成任务 |
| Goals Home 查询依赖增加成本 | 列表聚合变重 | 当前 P2 规模可接受，后续再批量优化 |

### 关键取舍

- 取舍 1：先做推荐下一步正确性，不做复杂路径规划。
- 取舍 2：不改 API 字段，只增强字段语义，降低前端改造成本。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Goal recommended next task 避开被依赖阻塞的任务 | 保证目标路径可执行 | P2 Goals 更贴近执行主线 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 增加 dependency-aware 推荐逻辑 | `app/services/goal_service.py` | Home / Detail 共用 |
| 2026-05-17 | 补充回归测试 | `tests/test_task_goal_services.py` | 覆盖阻塞和前置完成 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_task_goal_services tests.test_task_goal_api`
- [x] `uv run python scripts/verify_local.py --smoke p1-bearer-capture`
- [x] `git diff --check`

### 已知问题

- 暂无。

---

## 13. 后续迭代建议

- 检查 Strategy Detail 是否需要给 Goal 推荐下一步提供更轻量的“为什么先做这个”解释。
- 检查 Goals Home 在任务数量变多后是否需要批量预取依赖边。
