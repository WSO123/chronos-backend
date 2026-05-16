# Iteration: P2 Insight Detail

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-16  
> 负责人：Codex  
> 关联 PR / Issue / Commit：TBD

---

## 1. 迭代摘要

新增 `GET /api/v1/insights/detail`，为 Me -> Insights -> Insight Detail 提供轻量规则洞察，覆盖行为模式、高低效时段、任务安排建议和滚动策略补充说明。

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

P2 信息架构要求 `Insight Detail` 支持：

- 行为模式分析
- 高低效时段判断
- 任务安排优化建议
- 滚动策略解释

当前已有 Today、Strategy Detail、Weekly Report 和 Goals 聚合能力，可以先用规则聚合形成可信的轻量洞察，不等待真实 LLM。

### 目标

- 新增 Insights API / schema / service。
- 基于 Weekly Report、FocusSession、Task / Goal 状态生成 Insight Detail。
- 保持只读，不新增持久化 Insight 表。
- 不接真实 LLM，使用规则 fallback。

### 非目标

- 不实现 Energy / Health 数据接入。
- 不实现真实 LLM Insight Agent。
- 不实现可交互反馈 / 接受或忽略洞察。
- 不实现 Monthly Report。
- 不让 Insight Detail 替代 Today 的行动序列。

---

## 3. 产品约束对齐

### 核心路径

```text
Me -> Insights -> Insight Detail
```

- [ ] Capture
- [ ] Inbox
- [ ] Today
- [ ] Task Detail
- [ ] Focus
- [x] Report
- [x] Me
- [x] Goals
- [x] AI Agent

### 产品人格

- 轻盈：只返回一周内最关键的模式和建议。
- 克制：默认最多 5 个行为模式、3 条推荐、3 条策略说明。
- 可信赖：所有判断来自已有执行数据，不伪造健康 / 精力模型。
- 不施压：建议强调重新判断、保护重要任务和稳定节奏。
- 聪明但不炫耀：提供可解释信号，不展示复杂模型分数。

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
| Insight Detail API | 获取某周洞察详情 | Must | `anchor_date` 可选 |
| Overview | 汇总完成率、高价值完成、Focus、滞后和风险目标 | Must | 来自 Weekly Report |
| Behavior Patterns | 生成行为模式卡片 | Must | 规则判断 |
| Efficiency Windows | 按时段聚合 Focus 表现 | Should | 不是 Energy 模型 |
| Recommendations | 输出任务安排建议 | Should | 最多 3 条 |
| Strategy Notes | 给 Today 编排提供补充说明 | Could | 不直接修改计划 |

### 用户故事

```text
作为 Chronos 用户，
我希望在 Me 的 Insights 中看到本周行为模式，
以便知道下周应该保护什么、调整什么，而不是重新做一套复杂计划。
```

### 主要流程

```text
进入 Me
-> 打开 Insights
-> 查看 Insight Detail
-> 理解本周模式 / 优势时段 / 滞后风险
-> 回到 Today 继续执行
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

无。Insight Detail 是只读聚合，不新增数据库表。

### 状态机变更

无。

### 事件变更

不新增事件。读取已有 FocusSession / ActivityEvent / Task / Goal 数据。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/insights/detail` | 获取洞察详情 | `anchor_date` query，可选 | `InsightDetailResponse` |

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

- Agent 名称：Insight Generator fallback
- 输入对象：Weekly Report、FocusSession、Task、Goal
- 输出对象：InsightDetailResponse
- Pydantic schema：`InsightDetailResponse`
- fallback 策略：规则洞察
- 是否需要用户确认：不需要，只读反馈

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

说明：本迭代不调用真实 LLM，只预留后续 Insight Agent 的 response shape。

---

## 7. 验收标准

### 功能验收

- [x] 可以按 anchor date 返回所在周洞察。
- [x] 可以返回 overview。
- [x] 可以返回 behavior patterns。
- [x] 可以返回 efficiency windows。
- [x] 可以返回 recommendations 和 strategy notes。
- [x] 无数据时返回 insufficient_data 模式。

### 数据验收

- [x] 不新增业务表。
- [x] 不改变 Task / Goal / Today 状态。
- [x] 用户隔离正确。
- [x] 不把 Energy / Health 当成已存在数据源。

### 体验验收

- [x] 洞察帮助用户理解本周行为，而不是催促更多任务。
- [x] 默认信息不过载。
- [x] 建议克制可信。
- [x] 核心流程不因 AI 失败阻塞。

---

## 8. 测试计划

### 单元测试

- [x] Service 测试 Insight 聚合。

### API 测试

- [x] 正常路径。
- [x] 权限 / user_id 隔离。

### 集成测试

- [ ] DB migration：无新增 migration。
- [ ] Worker / AIJob：不涉及真实 worker。
- [x] fallback 路径：规则洞察。

### 手动验证

```text
1. 创建 high value task 和 overdue task。
2. 完成一次 Focus。
3. 调用 GET /api/v1/insights/detail?anchor_date=YYYY-MM-DD。
4. 确认 overview、behavior patterns、efficiency windows、recommendations 正确。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 规则洞察智能感有限 | 早期洞察可能比较朴素 | 先保证可信和可解释，后续接 Insight Agent |
| 时段判断数据少 | 可能无法判断真实高低效 | 明确 `no_data` / `visible` / `strong` 信号 |
| Insight Detail 信息偏多 | 可能抢走行动感 | 限制默认模式、推荐和策略说明数量 |

### 关键取舍

- 取舍 1：新增独立 `/insights/detail`，不塞进 Me Overview。
- 取舍 2：只做一周轻量洞察，不做 Monthly / 长期趋势。
- 取舍 3：不持久化 Insight，先验证反馈层价值。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-16 | Insight Detail 独立成 `insights` 模块 | 避免 Me Overview 变重 | Me 仍然轻 |
| 2026-05-16 | 使用 Weekly Report 作为 overview 来源 | 复用已有聚合口径 | 避免重复计算分叉 |
| 2026-05-16 | Efficiency Windows 只基于 FocusSession | 暂无 Energy / Health 数据 | 不伪造精力预测 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-16 | 新增 Insight schemas | `app/schemas/insights.py` | P2 response contract |
| 2026-05-16 | 新增 Insight service | `app/services/insight_service.py` | 规则聚合 |
| 2026-05-16 | 新增 Insight API | `app/api/v1/insights.py` | `GET /insights/detail` |
| 2026-05-16 | 注册 router | `app/api/v1/router.py` | API 生效 |
| 2026-05-16 | 补充测试 | `tests/test_insight_services.py`、`tests/test_insight_api.py` | service / API |
| 2026-05-16 | 更新文档 | `docs/chronos-backend-architecture-v1.md`、`docs/chronos-p1-frontend-api-contract.md` | 对齐接口 |

---

## 12. 验证结果

### 已验证

- [x] `python -m unittest tests.test_insight_services tests.test_insight_api`
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

- P2 Monthly Report：补长期趋势反馈。
- P2 Dependency View：补任务依赖解释。
- P3 Energy Dashboard：接入睡眠 / 压力后再增强效率时段判断。
