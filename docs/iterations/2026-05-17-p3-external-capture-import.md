# Iteration: P3 External Capture Import

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 关联提交：本轮提交

## 1. 迭代摘要

建立 Calendar / Email 外部条目进入 Chronos 的统一导入路径，让外部来源内容先进入 Capture / Inbox，而不是直接生成正式 Task。

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

上一轮 P3 已建立 Data Source 连接状态底座。下一步需要回答：连接后的外部条目如何进入 Chronos？

按照产品原则，外部来源不能绕过用户确认层直接写入 Task。Calendar / Email 条目应先进入 Capture / Inbox，再由用户确认、编辑或丢弃。

### 目标

- 新增 `ExternalCaptureImport` 模型，记录外部 item 与 Capture / Inbox 的映射。
- 新增 `POST /api/v1/captures/external-imports`。
- 支持 Calendar / Email 来源条目导入。
- 重复导入同一外部 item 时保持幂等。
- 用户确认 Inbox 后，Task source 保留为 `calendar` 或 `email`。

### 非目标

- 不接真实 Google Calendar / Gmail / Outlook API。
- 不实现同步调度器。
- 不支持 Health 数据导入。
- 不直接生成 Task / Goal。
- 不保存第三方 token。

## 3. 产品约束对齐

### 核心路径

```text
DataSourceConnection -> ExternalCaptureImport -> Capture -> Inbox -> Task / Goal
```

本轮服务 Capture / Inbox 输入层，也服务后续 Today 的外部任务来源。

### 用户故事

```text
作为一个会从日历和邮件中产生任务的用户，
我希望外部来源内容先进入待处理池，
以便我能确认它是否真的应该变成今天或未来的任务。
```

```text
作为一个不想被外部信息打断节奏的用户，
我希望 Chronos 不直接把日历和邮件变成正式任务，
以便我保留整理、编辑和丢弃的控制感。
```

### 开发者故事

```text
作为后续 Calendar / Email worker 的开发者，
我希望有一个统一、幂等的导入接口，
以便不同外部来源都能用同一条路径进入 Capture / Inbox。
```

### 设计护栏

- [x] 不让 Today 变成复杂驾驶舱
- [x] 不让 Task Detail 变成信息仓库
- [x] 不让 Focus 变成控制面板
- [x] 不让洞察和解释抢走行动感
- [x] 不让“聪明”压过“可信”

## 4. 需求范围

| 功能 | 描述 | 优先级 |
| --- | --- | --- |
| External Import Model | 记录外部 item 与 Capture / Inbox 映射 | Must |
| External Import API | Calendar / Email 条目导入入口 | Must |
| Idempotency | 同一外部 item 重复导入不重复创建 Capture / Inbox | Must |
| Source Preservation | Inbox 确认后 Task source 保留为 calendar / email | Must |
| ActivityEvent | 写入 `EXTERNAL_CAPTURE_IMPORTED` | Must |

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [x] Models
- [x] Schemas
- [x] DB Migration
- [x] Tests

### 数据模型

```text
ExternalCaptureImport {
  id
  user_id
  data_source_connection_id
  source
  provider
  external_item_id
  external_item_type
  title
  body
  occurred_at
  normalized_text
  external_payload
  capture_input_id
  inbox_item_id
}
```

### 状态机变更

无新增状态机。导入成功后仍复用：

```text
CaptureInput.received -> parsed
InboxItem.pending -> confirmed / edited / discarded
```

### 事件

- `EXTERNAL_CAPTURE_IMPORTED`
- 复用 `CAPTURE_CREATED`
- 复用 `CAPTURE_PARSED`
- 复用 `INBOX_ITEM_CREATED`

### API

| Method | Path | 用途 |
| --- | --- | --- |
| POST | `/api/v1/captures/external-imports` | 将外部 Calendar / Email item 导入 Capture / Inbox |

## 6. AI / LLM 影响

- [x] 不接真实 LLM
- [x] 复用当前 rule capture parser
- [x] 保留后续替换为真实 Capture Parser Agent 的接口空间

## 7. 验收标准

- Calendar / Email 连接可以导入外部 item。
- 导入后生成 `CaptureInput(input_type=external)`。
- 导入后生成 Pending InboxItem。
- 重复导入同一外部 item 不重复创建 Capture / Inbox。
- Paused / disconnected 数据源不能导入。
- Health 数据源不能走 Capture import。
- 用户确认外部 Inbox 后，Task source 保留 `calendar` / `email`。

## 8. 风险与后续

- 当前外部内容解析仍是规则 parser。
- 当前接口主要服务内部 worker，不是正式第三方 webhook。
- 后续需要 Calendar / Email worker 拉取真实数据并调用该接口。
- 后续需要 Task Detail 展示来源上下文。

## 9. 验证结果

| 验证项 | 结果 |
| --- | --- |
| `python -m unittest tests.test_external_capture_import_services tests.test_external_capture_import_api tests.test_capture_inbox_services tests.test_capture_inbox_api` | 19 tests OK |
| `python -m unittest discover -s tests` | 104 tests OK |
| `python -m compileall app tests scripts` | OK |
| `git diff --check` | OK |
| `alembic current` | `20260517_0009 (head)` |
| `scripts/smoke_p1_execution_loop.py` | OK |
| `scripts/smoke_p2_goal_insight_loop.py` | OK |
