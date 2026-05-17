# Iteration: P3 Today Strategy Energy Explanation

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

> 历史备注：本迭代记录的是 Energy 初次进入 Strategy Detail 时的只读边界。该边界已被 [P2 Planning Engine v1](./2026-05-17-p2-planning-engine-v1.md) 迭代推进：当前新 plan / replan 会把 Energy 作为排序和容量因子，但读 Strategy Detail 仍不会静默改版旧计划。

---

## 1. 迭代摘要

在 Today Strategy Detail 中增加只读 `energy` 解释块，让用户理解当日 Energy 数据对执行建议的参考意义，同时在本迭代完成时明确不会自动重排 Today。

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

P3 已完成 Energy Dashboard 和 Health worker。产品上 Energy 主要服务 Today 的 AI 排序与 Me 的洞察反馈，但本迭代完成时尚未让健康数据改变 Today，否则容易让 Today 变成复杂驾驶舱。因此先在 Strategy Detail 提供只读解释。

### 目标

- `GET /api/v1/today/strategy` 新增 `energy` 字段。
- 返回当天 Energy 数据是否存在、energy_level、recommended_mode 和解释文案。
- 本迭代完成时明确 `applied_to_plan=false`，不改变排序；后续 Planning Engine v1 已推进该边界。
- 补测试保证无数据和有数据路径都可解释。

### 非目标

- 不改变 Today planner 排序。
- 不重写 StrategySnapshot。
- 不新增 migration。
- 不引入 LLM。

---

## 3. 产品约束对齐

### 核心路径

```text
Me / Energy Dashboard -> Today Strategy Detail
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

Energy explanation 是用户主动进入 Strategy Detail 才看到的解释，不进入 Today 首屏，不制造压力，不炫耀智能。

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
| Strategy energy field | 返回 Energy 解释块 | Must | 只读 |
| No-data explanation | 无 Energy 数据时解释边界 | Must | 不影响排序 |
| Applied flag | 本迭代完成时返回 `applied_to_plan=false` | Must | 防止误解 |
| Tests | API 覆盖有/无数据 | Must | Today 不重排 |

### 用户故事

```text
作为 Chronos 用户，
我希望在查看今日策略解释时知道系统是否参考了精力状态，
以便信任系统边界，而不是担心健康数据偷偷改变安排。
```

```text
作为前端开发者，
我希望 Strategy Detail 明确返回 Energy 是否已应用到计划，
以便展示解释时不误导用户。
```

### 主要流程

```text
GET /today/strategy
-> build normal strategy detail
-> read same-day Energy dashboard
-> attach energy explanation
-> return without mutating DailyPlan
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

无。Strategy Detail 是只读解释接口。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/today/strategy` | 获取策略解释 | query `plan_date` | 新增 `energy` |

`energy`:

```text
{
  has_data
  metric_date
  energy_score
  energy_level
  recommended_mode
  explanation
  applied_to_plan
  source
}
```

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
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

说明：本轮为规则解释，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] 无 Energy 数据时返回 `has_data=false`。
- [x] 有 Energy 数据时返回 level 和 recommended_mode。
- [x] 本迭代完成时始终返回 `applied_to_plan=false`。
- [x] Task rationales 顺序不因 Energy 数据改变。

### 数据验收

- [x] 不修改 DailyPlan / DailyPlanItem。
- [x] 不新增 ActivityEvent。
- [x] user isolation 仍由原 Strategy Detail 路径保障。

### 体验验收

- [x] Energy 解释只在 Strategy Detail。
- [x] Today 首屏不增加复杂信息。
- [x] 文案明确“不自动重排 / 不自动增加任务量”。

---

## 8. 测试计划

### 单元测试

- [x] Strategy Detail no-data energy block。
- [x] Strategy Detail with energy data。

### API 测试

- [x] `GET /today/strategy` 返回 `energy`。

### 集成测试

- [x] 全量测试。
- [x] 编译检查。
- [x] Alembic head 检查。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 用户误以为 Energy 已参与排序 | 信任受损 | 本迭代完成时用 `applied_to_plan=false` 明确边界 |
| Strategy Detail 过载 | 解释抢走行动感 | 只加一个紧凑解释块 |
| 健康数据制造压力 | 违背产品人格 | 文案克制，不做惩罚式提示 |

### 关键取舍

- 取舍 1：先解释，不排序。
- 取舍 2：只在二级页展示，不进入 Today 首屏。
- 取舍 3：不更新 StrategySnapshot，避免历史计划被后台数据改写。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Strategy Detail 增加 energy block | P3 Energy 需要与 Today 建立解释性连接 | 用户能理解系统边界 |
| 2026-05-17 | `applied_to_plan=false` | 本迭代完成时不让 Energy 自动重排 | 后续已由 Planning Engine v1 单独推进 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 Strategy energy schema | `app/schemas/today.py` | response |
| 2026-05-17 | 新增 service 聚合 | `app/services/planning_service.py` | read-only |
| 2026-05-17 | 补测试 | `tests/test_today_api.py` | API |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | API contract |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_today_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] Energy 真正参与 Today 排序。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- Reminder Center P3 基础模型和只读 API。
- Notification settings / reminder worker。
- Energy-aware planning 正式排序因子，但必须提供用户可关闭策略。
