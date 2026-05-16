# Iteration: P3 Notification Settings

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

补齐 Me / Settings 的通知偏好接口，并让 deadline / execution reminder generator 遵守这些偏好，为后续真实通知发送建立可控边界。

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

Reminder Center、deadline generator 和 execution generator 已完成，但自动提醒如果没有用户偏好约束，后续接入真实发送时容易变得喧闹。产品人格要求 Chronos 温和、克制、可信，因此需要先建立提醒偏好的后端底座。

### 目标

- 扩展 `UserSettings`，保存提醒类型开关、channel 和默认提醒参数。
- 新增 `GET /api/v1/me/settings` 和 `PATCH /api/v1/me/settings`。
- deadline / execution generator 遵守用户通知偏好。
- Me overview 暴露基础提醒开关，方便 Settings 入口展示。

### 非目标

- 不接真实 push / email provider。
- 不做系统通知权限管理。
- 不做复杂规则引擎。
- 不让 Today 首屏展示完整设置。

---

## 3. 产品约束对齐

### 核心路径

```text
Me -> Settings -> Reminder Preferences -> Reminder Generators
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

本轮让用户能关掉或收紧自动提醒，保证 Chronos 的“聪明”不会越过用户控制感。

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
| Settings API | 读取 / 更新用户设置 | Must | Me / Settings |
| Reminder type preferences | execution / deadline 独立开关 | Must | generator 遵守 |
| Reminder channel preferences | in_app / push / email channel 开关 | Must | 当前只写记录 |
| Reminder defaults | execution limit / start / spacing / deadline hour | Must | worker 参数可覆盖 |

### 用户故事

```text
作为 Chronos 用户，
我希望能控制自动提醒的类型、数量和默认时间，
以便 Chronos 帮我开始行动，但不会制造额外打扰。
```

```text
作为后端开发者，
我希望 reminder generator 统一读取用户偏好，
以便后续接真实通知 provider 时不会绕过用户设置。
```

### 主要流程

```text
GET /me/settings
-> PATCH /me/settings
-> reminder.generate_deadline / reminder.generate_execution
-> read settings
-> create or skip reminders
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [x] Models
- [x] Schemas
- [x] Workers
- [ ] Agents
- [ ] Storage
- [x] DB Migration
- [x] Tests

### 数据模型变更

```text
UserSettings {
  reminder_execution_enabled
  reminder_deadline_enabled
  reminder_channel_in_app_enabled
  reminder_channel_push_enabled
  reminder_channel_email_enabled
  execution_reminder_limit
  execution_reminder_start_hour
  execution_reminder_spacing_minutes
  deadline_reminder_hour
}
```

### 状态机变更

无。

### 事件变更

无。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/me/settings` | 获取用户设置 | 无 | `UserSettingsResponse` |
| PATCH | `/api/v1/me/settings` | 局部更新用户设置 | `UserSettingsUpdate` | `UserSettingsResponse` |

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

说明：本轮是 settings / generator 规则约束，不调用 LLM。

---

## 7. 验收标准

### 功能验收

- [x] GET settings 会为用户创建默认设置。
- [x] PATCH settings 支持局部更新。
- [x] 至少保留一个 reminder channel。
- [x] execution generator 遵守全局和类型开关。
- [x] deadline generator 遵守全局和类型开关。
- [x] generator 使用 settings 默认提醒参数，worker 参数可覆盖。

### 数据验收

- [x] 新增字段有安全默认值。
- [x] settings 与 user 一对一。
- [x] 关闭偏好时不创建 reminder。

### 体验验收

- [x] 设置能力收敛在 Me / Settings。
- [x] Today 不新增复杂配置。
- [x] 自动提醒保持可解释和可关闭。

---

## 8. 测试计划

### 单元测试

- [x] reminder generator respects disabled preferences。
- [x] execution generator uses settings defaults。

### API 测试

- [x] GET /me/settings。
- [x] PATCH /me/settings。
- [x] 禁止关闭全部 channels。
- [x] Me overview settings 字段回归。

### 集成测试

- [x] 全量测试。
- [x] 编译检查。
- [x] Alembic SQL / head 检查。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 设置项过多 | Settings 变复杂 | 只暴露 reminder 必需开关和默认参数 |
| 关闭通知后仍生成提醒 | 信任受损 | generator 统一读取 UserSettings |
| channel 全关 | 后续发送无通道 | API 层禁止全部关闭 |

### 关键取舍

- 取舍 1：先做偏好底座，不做真实通知 provider。
- 取舍 2：channel 当前只影响 reminder 记录，不发送。
- 取舍 3：worker 参数可覆盖默认值，便于后续定时调度微调。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Settings API 放在 `/me/settings` | Settings 是 Me 的二级页 | 不新增一级 Settings 模块 |
| 2026-05-17 | 至少保留一个 reminder channel | 保证后续 delivery provider 有默认通道 | 用户可关类型，但不关掉所有通道 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 扩展 UserSettings | `app/models/user.py` / Alembic | reminder preferences |
| 2026-05-17 | 新增 Settings API | `app/api/v1/me.py` | GET / PATCH |
| 2026-05-17 | 新增 settings service/schema | `app/services/settings_service.py` / `app/schemas/settings.py` | defaults / validation |
| 2026-05-17 | generator 遵守偏好 | `app/services/reminder_service.py` | deadline / execution |
| 2026-05-17 | 补测试 | `tests/test_settings_api.py` / `tests/test_reminder_services.py` | API / service |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_settings_api tests.test_reminder_services tests.test_report_me_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `uv run alembic upgrade head --sql`
- [x] `uv run alembic upgrade head`
- [x] `git diff --check`

### 未验证

- [ ] 真实 push / email delivery provider。
- [ ] 前端 Settings 页面。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- Delivery provider abstraction：把 dispatch_due 从状态流转扩展为 provider payload 发送。
- Reminder Center pending count：给 Today Header 提供轻量提醒入口数字。
- Scheduler plan：定义哪些 worker 以什么频率运行。
