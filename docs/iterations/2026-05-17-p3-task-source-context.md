# Iteration: P3 Task Detail Source Context

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Task Detail 增加轻量来源上下文，让用户在执行前知道外部任务来自 Calendar / Email，但不把 Task Detail 扩展成来源信息仓库。

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

上一轮已完成 External Capture Import：Calendar / Email 条目可进入 Capture / Inbox，用户确认后生成带 `calendar` / `email` 来源的 Task。按照 P3 信息架构，Task Detail 需要在 Related Context / Basic Info 区域承接来源内容，但产品约束要求它仍是执行前承接层，不能变成信息仓库。

### 目标

- `GET /api/v1/tasks/{task_id}` 对外部导入任务返回 `source_context`。
- `source_context` 只包含来源摘要、外部标题、正文预览和关联 id。
- 手动任务、普通 Capture 任务默认返回 `source_context=null`。

### 非目标

- 不接真实第三方 Calendar / Email API。
- 不展示完整邮件正文、完整日历对象、`external_payload` 或 `normalized_text`。
- 不新增独立来源详情页接口。
- 不改变 Inbox 确认状态机。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [x] Capture
- [x] Inbox
- [ ] Today
- [x] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

本次迭代把外部来源解释成一张轻量上下文卡：用户能理解“任务从哪里来”，但不会被完整来源数据打断执行。它符合 Chronos 的克制、可信赖、有判断的产品人格。

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
| Task Detail source_context | 外部导入任务返回轻量来源上下文 | Must | Calendar / Email |
| 来源预览裁剪 | 只返回正文预览，避免信息过载 | Must | 默认 180 字符 |
| 普通任务空上下文 | 手动 / 普通 Capture 任务返回 `null` | Must | 保持轻量 |
| P3 合同文档更新 | 前端可按合同渲染来源卡 | Must | 不展开到 Today |

### 用户故事

```text
作为 Chronos 用户，
我希望在 Task Detail 里快速知道一个任务来自哪个日历或邮件条目，
以便我信任这个任务的来源并决定是否开始执行。
```

```text
作为前端开发者，
我希望 Task Detail 返回稳定、轻量的 source_context，
以便我能渲染来源卡，而不需要读取外部平台原始 payload。
```

```text
作为后端系统，
我希望通过 Inbox 确认结果反查 ExternalCaptureImport，
以便保持 Capture -> Inbox -> Task 的可追溯链路。
```

### 主要流程

```text
Calendar / Email item
-> External Capture Import
-> Capture / Inbox
-> 用户确认 Inbox
-> 生成 Task(source=calendar/email)
-> GET Task Detail
-> 返回 source_context
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

复用上一轮事件：

- `EXTERNAL_CAPTURE_IMPORTED`
- `INBOX_ITEM_CONFIRMED`
- `TASK_CREATED`

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/tasks/{task_id}` | Task Detail 来源上下文 | - | 增加 `source_context` |

`source_context` 字段：

```json
{
  "source": "calendar",
  "capture_source": "calendar",
  "provider": "google_calendar",
  "external_item_id": "calendar-event-123",
  "external_item_type": "calendar_event",
  "external_title": "完成项目复盘",
  "external_body_preview": "整理会议结论",
  "occurred_at": "2026-05-17T09:00:00Z",
  "imported_at": "2026-05-17T09:05:00Z",
  "capture_input_id": "uuid",
  "inbox_item_id": "uuid",
  "data_source_connection_id": "uuid"
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

说明：本轮没有新增 LLM 行为，上述边界沿用现有架构约束。

---

## 7. 验收标准

### 功能验收

- [x] 外部 Calendar 任务的 Task Detail 返回来源上下文。
- [x] 普通手动任务的 Task Detail 返回 `source_context=null`。
- [x] API 响应不包含 `external_payload` 和 `normalized_text`。

### 数据验收

- [x] 不新增数据表。
- [x] 不改变 Inbox 确认状态机。
- [x] 来源上下文可追溯到 `capture_input_id`、`inbox_item_id`、`data_source_connection_id`。

### 体验验收

- [x] 用户能清楚知道下一步。
- [x] 页面默认信息不过载。
- [x] 来源解释克制可信。
- [x] 核心流程不因 AI 失败阻塞。

---

## 8. 测试计划

### 单元测试

- [x] Service 测试：Task Detail 返回外部来源上下文。
- [x] Service 测试：普通任务不返回来源上下文。

### API 测试

- [x] API 测试：External Import -> Inbox Confirm -> Task Detail。
- [x] API 测试：响应不泄露原始 payload / normalized_text。

### 集成测试

- [ ] DB migration：本轮无 migration。
- [ ] Worker / AIJob：本轮无 worker / AIJob。

### 手动验证

```text
1. 创建 calendar data source placeholder。
2. POST external import。
3. confirm inbox item。
4. GET task detail，检查 source_context。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Task Detail 字段继续膨胀 | 违背产品约束 | 只返回摘要和 id，不返回原始 payload |
| 外部导入记录缺失 | 任务 source 存在但无法展示来源卡 | 返回 `source_context=null`，不阻塞 Task Detail |
| 后续需要完整来源详情 | Task Detail 不应继续扩展 | 后续新增独立来源详情接口 |

### 关键取舍

- 取舍 1：通过 Inbox 确认结果反查 ExternalCaptureImport，而不是在 Task 表冗余外部来源字段。
- 取舍 2：正文只返回预览，不返回完整 body / payload，保护 Task Detail 的执行感。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Task Detail 只承接轻量 source_context | 符合“承接层但非信息仓库”的约束 | 完整来源详情后续单独接口承接 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 增加 source_context 聚合 | `app/services/task_service.py` | 通过 Inbox 结果反查 ExternalCaptureImport |
| 2026-05-17 | 增加响应 schema | `app/schemas/tasks.py` | `TaskSourceContextResponse` |
| 2026-05-17 | 增加测试 | `tests/test_task_goal_services.py`, `tests/test_external_capture_import_api.py` | 覆盖 service / API |
| 2026-05-17 | 更新开发文档 | `docs/chronos-p3-frontend-api-contract.md`, `docs/chronos-backend-architecture-v1.md` | 对齐 P3 合同 |

---

## 12. 验证结果

开发完成后填写。

### 已验证

- [x] `uv run python -m unittest tests.test_task_goal_services tests.test_external_capture_import_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

### 未验证

- [ ] 真实第三方 Calendar / Email 同步。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- P3 Calendar / Email connector worker 占位同步任务。
- 独立来源详情接口，用于展示完整邮件 / 日历上下文。
- Energy Dashboard 数据导入，服务 Today 精力辅助排序。
