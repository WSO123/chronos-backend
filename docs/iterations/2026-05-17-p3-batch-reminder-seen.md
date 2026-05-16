# Iteration: P3 Batch Reminder Seen

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 `POST /api/v1/reminders/seen` 批量已看接口，让 Reminder Center 可以一次性清理未看数，同时保持 seen 与 dismiss 的语义区分。

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

单条 seen 接口适合用户逐条查看，但 Reminder Center 打开时常见交互是批量清除未看数字。如果前端逐条调用，会增加请求数量并制造不必要复杂度。本轮补批量接口。

### 目标

- 新增 batch seen schema / API。
- 支持最多 100 个 reminder ids。
- 去重重复 ids。
- 跨用户 id 返回 NotFound，保护隔离。

### 非目标

- 不批量 dismiss。
- 不自动 seen。
- 不改变 Reminder 主状态。
- 不新增 unread 状态枚举。

---

## 3. 产品约束对齐

### 核心路径

```text
Reminder Center -> Batch Seen -> Today Header unseen count
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

Batch seen 是降低界面噪音的轻量动作，不删除提醒、不强迫用户处理提醒。

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
| Batch seen API | 批量标记 seen | Must | 1..100 ids |
| Deduplicate ids | 重复 id 只处理一次 | Must | 保持计数准确 |
| Ownership check | 任一 id 越权返回 NotFound | Must | 用户隔离 |
| Response counts | updated / already_seen | Must | 前端更新数字 |

### 用户故事

```text
作为 Chronos 用户，
我希望打开 Reminder Center 后能一次清除未看数字，
以便 Today Header 保持安静。
```

```text
作为前端开发者，
我希望可以批量标记 reminders seen，
以便不需要为每条提醒发一次请求。
```

### 主要流程

```text
POST /reminders/seen
-> validate ids
-> verify ownership
-> set seen_at for unseen reminders
-> return counts
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

无。`seen_at` 不改变 `status`。

### 事件变更

无。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/reminders/seen` | 批量标记已看 | reminder_ids | counts + reminders |

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

说明：本轮是 Reminder Center 批量操作，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] 可批量 mark seen。
- [x] 重复 id 去重。
- [x] already seen 计入 already_seen_count。
- [x] 越权 id 返回 NotFound。

### 数据验收

- [x] 不改变 status。
- [x] 不新增 migration。

### 体验验收

- [x] 支持 Reminder Center 一次清理未看数。
- [x] 不删除提醒。

---

## 8. 测试计划

### 单元测试

- [x] batch seen service。
- [x] cross-user rejection。

### API 测试

- [x] POST /reminders/seen。

### 集成测试

- [x] 全量测试。
- [x] 编译检查。
- [x] Alembic head 检查。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 批量越权泄露 | 安全风险 | 任一缺失统一 NotFound |
| ids 过多 | 请求过重 | schema 限制最多 100 |
| 前端误用为 dismiss | 用户提醒仍存在 | API 命名 seen，不改变 status |

### 关键取舍

- 取舍 1：批量 seen all-or-nothing。
- 取舍 2：返回 reminders，方便前端同步局部状态。
- 取舍 3：不做批量 dismiss。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Batch seen 最多 100 条 | 控制请求复杂度 | 大列表需分页处理 |
| 2026-05-17 | 任一越权统一 NotFound | 避免泄露跨用户存在性 | 前端需传当前用户 ids |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 batch seen schema/API/service | Reminder modules | bulk operation |
| 2026-05-17 | 补测试 | Reminder service / API | dedupe / isolation |
| 2026-05-17 | 更新文档 | Architecture / P3 contract | batch seen |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_reminder_services tests.test_reminder_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 前端 Reminder Center 批量接入。

### 已知问题

- 暂无批量 dismiss。

---

## 13. 后续迭代建议

- P3 stabilization review。
- Calendar provider adapter hardening。
- External import duplicate observability。
