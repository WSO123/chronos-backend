# Iteration: P3 Reminder Center Filters

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Reminder Center 列表增加轻量过滤：按提醒类型、是否到期、是否未读筛选，便于前端渲染执行提醒 / 截止提醒 / 未读提醒视图。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

Reminder Center 已支持基础列表、summary、seen、snooze 和 dismiss。但列表只能按 status 过滤，不足以支持 P3 信息架构中的执行提醒、截止提醒和未读提示入口。

### 目标

- `GET /api/v1/reminders` 支持 `reminder_type`。
- 支持 `due_only` 与 `unseen_only`。
- `due_only` 支持传入 `now`，便于测试和前端一致性。
- `scheduled_count` / `overdue_count` 仍保持用户全局计数，不被列表过滤改变。

### 非目标

- 不做复杂搜索。
- 不新增排序选项。
- 不新增 reminder 状态。
- 不做分组聚合。

---

## 3. 产品约束对齐

### 核心路径

```text
Reminder Center -> Filtered List -> Lightweight Action
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

过滤只帮助用户快速找到需要处理的提醒，不把 Reminder Center 做成复杂任务控制台。

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
| Type filter | `reminder_type=execution/deadline/...` | Must | 校验合法类型 |
| Due filter | `due_only=true&now=...` | Must | 不改 summary |
| Unseen filter | `unseen_only=true` | Must | 基于 `seen_at` |
| Tests | service / API 测试 | Must | 保持全局计数 |

### 用户故事

```text
作为 Chronos 用户，
我希望可以快速查看未读、已到期或某类提醒，
以便我不用在 Reminder Center 里扫描所有消息。
```

```text
作为前端开发者，
我希望 Reminder Center 列表有轻量过滤参数，
以便实现顶部 tabs 或筛选 chips 时不需要前端本地过滤。
```

### 主要流程

```text
GET /reminders?reminder_type=execution&due_only=true&unseen_only=true
-> service validates filters
-> returns filtered reminders
-> returns global scheduled / overdue counts
```

---

## 5. 后端设计

### 影响模块

- [x] API
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

无。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/reminders` | 列出提醒 | `status/reminder_type/due_only/unseen_only/now/limit/offset` | `ReminderListResponse` |

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

说明：本轮只改列表过滤，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] 可按 reminder_type 过滤。
- [x] 可只返回 due reminders。
- [x] 可只返回 unseen reminders。
- [x] 非法 reminder_type 返回 validation error。
- [x] `scheduled_count` / `overdue_count` 不受过滤影响。

### 数据验收

- [x] 不写数据库。
- [x] 不新增 schema。

### 体验验收

- [x] Reminder Center 更易扫描。
- [x] 不增加用户操作复杂度。

---

## 8. 测试计划

### 单元测试

- [x] reminder service filters。

### API 测试

- [x] reminder list filters。

### 集成测试

- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 过滤项过多 | Reminder Center 变复杂 | 只保留类型、due、unseen 三类基础过滤 |
| 计数语义混淆 | Header count 与列表不一致 | 明确 count 为全局计数 |
| due 判断时区问题 | 前端感知不一致 | 接口可传 `now`，后端统一转 UTC |

### 关键取舍

本轮只做 Reminder Center 的基础扫描能力，不引入搜索、排序、分组和复杂聚合。

---

## 10. Review 记录

### 自检结论

- 与 Reminder Center P3 信息架构一致。
- 与产品人格一致：帮助扫描，不增加压力。
- 与工程规范一致：过滤逻辑在 service，不放在 router。

### 后续建议

- 若前端需要 tabs，可直接映射 `reminder_type` / `due_only` / `unseen_only`。
