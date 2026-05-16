# Iteration: P2 Strategy Detail

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-16  
> 负责人：Codex  
> 关联 PR / Issue / Commit：TBD

---

## 1. 迭代摘要

新增 Today 的 Strategy Detail 只读解释接口，让用户在需要时理解 AI / rule planner 为什么这样安排今天，同时保持 Today 首页轻盈，不把策略解释变成复杂驾驶舱。

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

信息架构里 Today 有 `AI Strategy Card`，P2 有 `Strategy Detail`。P1 Today 默认只返回策略摘要，不暴露复杂 score factors。进入 P2 后，需要给用户一个可信但克制的解释入口，让用户知道系统如何保护高价值任务、如何选择轻量 / 常规 / 冲刺模式，并理解任务排序理由。

### 目标

- 新增 `GET /api/v1/today/strategy`。
- 返回当前 Today plan 的 strategy snapshot、PlanRevision、轻量 factors、解释文案和任务推荐理由。
- 不重新排序，不改变 Task / Goal 状态；无 plan 时与 `GET /today` 一致 lazy create。
- 不新增数据库表，不接真实 LLM。

### 非目标

- 不实现真实 LLM Strategy Explainer。
- 不提供重新排序 / 调整优先级动作。
- 不暴露完整 score 计算细节。
- 不实现历史 strategy diff 页面。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [ ] Goals
- [x] AI Agent

### 产品人格

- 轻盈：Today 首页仍只展示摘要，详情页按需打开。
- 克制：解释文案短句化，factors 只做信任支撑。
- 可信赖：解释来自已持久化的 `StrategySnapshot` 和 `PlanRevision`。
- 不施压：解释为什么这样排，而不是催促用户多做。
- 聪明但不炫耀：展示可理解的策略因素，不展示复杂评分引擎。

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
| Strategy Detail API | 获取当前 Today 策略解释 | Must | `plan_date` 可选 |
| Revision Metadata | 返回当前 PlanRevision 信息 | Must | 帮助解释策略生成来源 |
| Strategy Factors | 返回轻量因素统计 | Must | 不展示完整 score factors |
| Explanation | 返回短解释列表 | Should | 规则生成 |
| Task Rationales | 返回当前任务推荐理由 | Should | 复用 Today item response |

### 用户故事

```text
作为 Chronos 用户，
我希望在不打断行动的前提下理解 Today 为什么这样安排，
以便建立对 AI 编排的信任，并在必要时决定是否 replan。
```

### 主要流程

```text
进入 Today
-> 查看 AI Strategy Card
-> 打开 Strategy Detail
-> 查看策略解释 / factors / 任务推荐理由
-> 返回 Today 执行
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

无。复用：

```text
DailyPlan
PlanRevision
StrategySnapshot
DailyPlanItem
Task
```

### 状态机变更

无。

### 事件变更

不新增事件。Strategy Detail 是只读解释接口。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/today/strategy` | 获取当前 Today 策略解释 | `plan_date` query，可选 | `StrategyDetailResponse` |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [x] 不涉及真实 LLM 调用
- [ ] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [x] 使用已有规则 fallback 输出

### Agent 设计

- Agent 名称：Daily Planner 规则输出 / Strategy Explainer fallback
- 输入对象：DailyPlan、PlanRevision、StrategySnapshot、DailyPlanItem
- 输出对象：StrategyDetailResponse
- Pydantic schema：`StrategyDetailResponse`
- fallback 策略：规则生成 explanation
- 是否需要用户确认：不需要，只读解释

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

说明：本迭代不调用真实 LLM，只为后续 Strategy Explainer 预留 response shape。

---

## 7. 验收标准

### 功能验收

- [x] 可以获取某天 active plan 的 Strategy Detail。
- [x] 无 plan 时与 Today 一致，lazy create 当日 plan。
- [x] 返回 revision、factors、explanation、task_rationales 和 source。
- [x] Today 默认 response 不新增复杂 factors。

### 数据验收

- [x] 不新增业务表。
- [x] 不改变 Task / Goal 状态。
- [x] 无 plan 时 lazy create 行为与 `GET /today` 一致。
- [x] 用户隔离正确。
- [x] explanation 来自当前 strategy snapshot 和当前 plan items。

### 体验验收

- [x] 用户能理解今天为什么这样排。
- [x] 默认信息不过载。
- [x] 策略解释克制可信。
- [x] 核心流程不因 AI 失败阻塞。

---

## 8. 测试计划

### 单元测试

- [x] Service 测试 Strategy Detail 聚合。

### API 测试

- [x] 正常路径。
- [x] 权限 / user_id 隔离。

### 集成测试

- [ ] DB migration：无新增 migration。
- [ ] Worker / AIJob：不涉及真实 worker。
- [x] fallback 路径：规则解释。

### 手动验证

```text
1. 创建 high value task 和 low priority task。
2. 调用 GET /api/v1/today/strategy?plan_date=YYYY-MM-DD。
3. 确认 factors、explanation、task_rationales 与 Today 当前序列一致。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| factors 过多 | 前端可能做成驾驶舱 | 文档明确只默认展示少量核心字段 |
| explanation 仍是规则文案 | 智能感有限 | 后续可接 Strategy Explainer Agent |
| task_rationales 返回当前 items | 任务多时信息偏多 | 前端默认折叠，只按需展开 |

### 关键取舍

- 取舍 1：接口放在 `/today/strategy`，因为它属于 Today 的二级解释页。
- 取舍 2：复用 `StrategySnapshot`，不新增策略解释表。
- 取舍 3：解释接口不提供动作，避免抢走 Today 的行动感。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-16 | Strategy Detail 使用只读聚合 | 保持轻盈可信 | 无 migration |
| 2026-05-16 | Today 默认不返回 factors | 避免首页驾驶舱化 | 需要单独调用详情接口 |
| 2026-05-16 | 无 plan 时 lazy create | 与 `GET /today` 行为一致 | 直接打开详情页不会失败 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-16 | 新增 Strategy Detail schema | `app/schemas/today.py` | P2 response contract |
| 2026-05-16 | 新增 Strategy Detail service | `app/services/planning_service.py` | 只读聚合 |
| 2026-05-16 | 新增 API | `app/api/v1/today.py` | `GET /today/strategy` |
| 2026-05-16 | 补充测试 | `tests/test_today_services.py`、`tests/test_today_api.py` | service / API |
| 2026-05-16 | 更新文档 | `docs/chronos-backend-architecture-v1.md`、`docs/chronos-p1-frontend-api-contract.md` | 对齐接口 |

---

## 12. 验证结果

### 已验证

- [x] `python -m unittest tests.test_today_services tests.test_today_api`
- [x] `python -m unittest discover -s tests`
- [x] `python -m compileall app tests scripts`
- [x] `git diff --check`
- [x] `python scripts/smoke_p1_execution_loop.py`

### 未验证

- [ ] 真实前端联调。

### 已知问题

- 暂无。

---

## 13. 后续迭代建议

- P2 Insight Detail：基于 Reports / Strategy / Goal 数据沉淀行为洞察。
- P2 Monthly Report：补长期趋势反馈。
- P2 Dependency View：补目标任务依赖解释。
