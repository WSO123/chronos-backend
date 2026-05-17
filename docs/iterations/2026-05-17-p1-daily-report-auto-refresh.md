# Iteration: P1 Daily Report Auto Refresh

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让 `GET /reports/daily` 在执行指标变化时刷新同一条 Daily Report，避免用户完成 Focus 后看到旧的复盘数据。

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

P1 的反馈闭环是 `Focus -> Today -> Daily Report`。此前 `GET /reports/daily` 如果发现当天 report 已存在，会直接返回旧记录。若用户先打开过 Daily Report，然后又完成 Focus，再次 GET 可能拿到旧完成数和旧 Focus 时长，需要前端知道去调用 `POST /generate` 才能刷新。这会让反馈层不够可信。

### 目标

- `GET /reports/daily` 在 report 已存在时重新计算关键 metrics。
- 如果 metrics 未变化，保持幂等返回。
- 如果 metrics 已变化，刷新同一条 report，不创建重复 report。

### 非目标

- 不新增复杂洞察。
- 不改变 Weekly / Monthly 聚合。
- 不引入新的 Agent。
- 不做前端页面。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Task Detail -> Focus -> Daily Report
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [x] Task Detail
- [x] Focus
- [x] Report
- [ ] Me
- [ ] Goals
- [x] AI Agent

### 产品人格

- 轻盈：前端 GET 即可拿到当前复盘，不需要额外判断。
- 克制：只比较关键执行指标，不做复杂实时分析。
- 可信赖：Focus 完成后 Daily Report 不返回旧数据。
- 聪明但不炫耀：Agent 仍只生成复盘文案，不修改事实指标。

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
| Report metric comparison | GET 时比较 report 与当前 metrics | Must | 完成数 / 延后数 / 中断数 / Focus 时长 / plan version |
| Auto refresh same report | 指标变化时刷新同一条 Daily Report | Must | 不重复创建 |
| Contract update | 文档说明 GET 会自动刷新关键指标 | Should | 前端联调 |

### 用户故事

```text
作为刚完成 Focus 的用户，
我希望打开 Daily Report 时看到最新完成数和专注时长，
以便复盘反馈和刚刚的执行行为一致。
```

```text
作为前端开发者，
我希望 GET /reports/daily 能返回当前数据，
以便不用在普通查看和强制刷新之间做额外判断。
```

### 主要流程

```text
GET /reports/daily
-> 生成初始 report
-> 用户完成 Focus
-> GET /reports/daily
-> 后端比较 metrics
-> 刷新同一条 report
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [ ] Models
- [ ] Schemas
- [ ] Workers
- [x] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

无新增事件。刷新仍复用既有 Daily Report 生成事件。

### API 变更

无字段变更。既有接口行为增强：

| Method | Path | 变化 |
| --- | --- | --- |
| GET | `/api/v1/reports/daily` | report 已存在但 metrics 变化时自动刷新 |
| POST | `/api/v1/reports/daily/generate` | 保持显式强制刷新入口 |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

- Agent 名称：Daily Report Agent
- 输入对象：重新计算后的 DailyReportMetrics
- 输出对象：复盘 summary / suggestions
- fallback 策略：保留既有规则文案
- 是否需要用户确认：否，Agent 不修改事实指标

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] report 未变化时 GET 保持幂等。
- [x] report 已存在且 Focus 完成后，GET 刷新同一条 report。
- [x] 刷新后完成数和 Focus 时长更新。

### 数据验收

- [x] 不重复创建 DailyReport。
- [x] `completed_task_count` 更新。
- [x] `focus_minutes` 更新。
- [x] `refreshed_at` 更新。

### 体验验收

- [x] 前端普通 GET 即可拿到最新复盘。
- [x] Report 仍保持轻量反馈层，不变成复杂洞察页。

---

## 8. 测试计划

### 单元 / API 测试

- [x] `tests.test_report_me_services`
- [x] `tests.test_report_me_api`
- [x] `tests.test_focus_services`
- [x] `tests.test_focus_api`

### Smoke

- [x] `scripts/verify_local.py --smoke p1-bearer-capture`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| GET 触发 Agent 导致成本增加 | 高频访问 report 可能多跑 Agent | 仅 metrics 变化时刷新 |
| 复盘文案随 GET 改变 | 用户看到文案变化 | 事实指标变化时刷新是合理行为，显式 generate 仍保留 |

### 关键取舍

- 取舍 1：GET daily report 保证当前性，优先服务 P1 闭环可信度。
- 取舍 2：只比较关键指标，不引入复杂脏标记系统。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | GET Daily Report 在 metrics 变化时自动刷新 | 避免 Focus 后复盘旧数据 | P1 反馈闭环更可靠 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 增加 report metrics 比较 | `app/services/report_service.py` | 自动刷新同一条 report |
| 2026-05-17 | 补充回归测试 | `tests/test_report_me_services.py` | 覆盖先生成 report 后完成 Focus |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_report_me_services tests.test_report_me_api tests.test_focus_services tests.test_focus_api`
- [x] `uv run python scripts/verify_local.py --smoke p1-bearer-capture`
- [x] `git diff --check`

### 已知问题

- 暂无。

---

## 13. 后续迭代建议

- 检查 Daily Report 的 Agent 调用频率是否需要后续增加轻量节流或缓存策略。
- 检查 Insight Detail 是否应复用 Daily Report 的最新 metrics，避免重复计算。
