# Iteration: P1 Capture / Inbox

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-16  
> 负责人：Chronos Team  
> 关联 PR / Issue / Commit：

---

## 1. 迭代摘要

实现 Chronos P1 的文本 Capture / Inbox 闭环，让用户可以把临时输入先进入待处理池，再确认生成正式 Task / Goal。

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

Task / Light Goal API 已经可以承载正式任务和目标。下一步需要接入输入缓冲层：Capture 接收原始文本，规则解析生成候选结果，Inbox 让用户确认、编辑或丢弃，避免 AI / parser 直接污染正式任务库。

### 目标

- 新增 `CaptureInput`、`AIParseResult`、`InboxItem` 模型和 migration。
- 实现文本 Capture API。
- 实现 Inbox 列表、详情、编辑、确认、丢弃 API。
- P1 使用 rule/mock parser，不接真实 LLM。
- Confirm 复用现有 Task / Goal service，保证事件和状态一致，并避免重复确认生成重复对象。

### 非目标

- 不支持语音 / 图片 / 邮件 / 日历输入。
- 不接入真实 LLM。
- 不做异步 Celery 解析。
- 不实现复杂 Goal 关联推荐。
- 不实现 Today / DailyPlan。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [x] Capture
- [x] Inbox
- [ ] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

本迭代把解析复杂度藏在系统内部，但不让系统替用户直接决定正式任务。用户在 Inbox 保留确认、编辑、丢弃的控制权。

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
| Capture API | 创建文本输入、查询输入 | Must | P1 仅文本 |
| Rule parser | 根据文本生成候选 Task / Goal / unknown | Must | 后续替换为 LLM Agent |
| Inbox API | 列表、详情、编辑、确认、丢弃 | Must | 用户确认层 |
| Confirm Task | InboxItem 确认生成 Task | Must | 复用 TaskService |
| Confirm Goal | InboxItem 确认生成 Goal | Must | 复用 GoalService |

### 用户故事

```text
作为 Chronos 用户，
我希望可以快速输入一段文本，
让系统先整理到 Inbox，
再由我确认生成任务或目标，
以便降低输入成本但保留控制感。
```

### 主要流程

```text
POST /captures
-> CaptureInput
-> rule parser
-> AIParseResult
-> InboxItem
-> PATCH /inbox/{id}
-> POST /inbox/{id}/confirm
-> Task / Goal
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [x] Models
- [x] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [x] DB Migration
- [x] Tests

### 数据模型变更

新增：

```text
CaptureInput
AIParseResult
InboxItem
```

### 状态机变更

```text
CaptureInput.received -> parsed
CaptureInput.received -> failed
InboxItem.pending -> edited
InboxItem.pending -> confirmed
InboxItem.edited -> confirmed
InboxItem.confirmed -> confirmed      // idempotent return
InboxItem.pending -> discarded
InboxItem.edited -> discarded
```

### 事件变更

- CAPTURE_CREATED
- CAPTURE_PARSED
- INBOX_ITEM_CREATED
- INBOX_ITEM_UPDATED
- INBOX_ITEM_CONFIRMED
- INBOX_ITEM_DISCARDED

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/captures` | 创建文本输入并解析 | CaptureCreate | CaptureCreateResponse |
| GET | `/api/v1/captures/{capture_id}` | 查询输入 | - | CaptureResponse |
| GET | `/api/v1/inbox` | 查询待处理池 | `status` / `include_all` / `limit` / `offset` | InboxItemResponse[] |
| GET | `/api/v1/inbox/{item_id}` | 查询待处理项 | - | InboxItemResponse |
| PATCH | `/api/v1/inbox/{item_id}` | 编辑待处理项 | InboxItemUpdate | InboxItemResponse |
| POST | `/api/v1/inbox/{item_id}/confirm` | 确认生成 Task / Goal | - | InboxConfirmResponse |
| POST | `/api/v1/inbox/{item_id}/discard` | 丢弃待处理项 | - | InboxItemResponse |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及 mock/rule Agent
- [ ] 新增 Agent
- [ ] 修改真实 LLM Prompt
- [x] 定义 Structured Output 形态
- [x] 修改 fallback

### Agent 设计

P1 不接真实 LLM。`CaptureParser` 先用 rule/mock 版本：

- 输入对象：`CaptureInput`
- 输出对象：`AIParseResult`、`InboxItem`
- fallback：生成 `unknown` InboxItem
- 是否需要用户确认：是

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [ ] AIJob 状态可查询（P1 同步 rule parser 暂不创建 AIJob，异步 LLM 接入时补齐）
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] 可以创建文本 Capture。
- [x] Capture 自动生成 AIParseResult 和 InboxItem。
- [x] 可以列表 / 详情查看 InboxItem。
- [x] 可以编辑 InboxItem。
- [x] 可以确认生成 Task / Goal。
- [x] 可以丢弃 InboxItem。
- [x] 不同 `X-User-Id` 之间数据隔离。

### 数据验收

- [x] Capture / parse / inbox 数据正确落库。
- [x] Confirm 后正式 Task / Goal 正确生成。
- [x] Confirm 幂等返回既有结果，不重复创建正式对象；discard 后不可 confirm。
- [x] 关键动作写入 `ActivityEvent`。

### 体验验收

- [x] Parser 低置信度结果进入 Inbox，而不是直接创建正式对象。
- [x] 用户可以编辑后确认。
- [x] 核心流程不依赖真实 LLM。

---

## 8. 测试计划

### 单元测试

- [x] CaptureService 创建文本输入
- [x] Rule parser 输出 Task / Goal / unknown
- [x] InboxService 编辑 / 确认 / 丢弃
- [x] ActivityEvent 写入

### API 测试

- [x] Capture happy path
- [x] Inbox confirm Task
- [x] Inbox confirm Goal
- [x] Inbox discard
- [x] 404 / invalid state
- [x] user_id 隔离

### 集成测试

- [x] Alembic migration 可生成 SQL
- [x] FastAPI dependency override

### 手动验证

```text
1. POST /api/v1/captures 创建文本输入。
2. GET /api/v1/inbox 查看待处理项。
3. PATCH /api/v1/inbox/{id} 编辑。
4. POST /api/v1/inbox/{id}/confirm 生成 Task / Goal。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| rule parser 简单 | 解析不够智能 | P1 保证闭环，后续替换 LLM |
| 同步解析 | 创建 Capture 时会立即生成 InboxItem | P1 简化，后续 AIJob + worker |
| unknown 结果较多 | 用户需要手动编辑 | 保留编辑和确认权 |

### 关键取舍

- P1 先同步 rule parse，不引入异步 worker。
- Capture 不直接生成正式 Task / Goal。
- Confirm 必须经过 Inbox。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-16 | P1 使用 rule parser | 保证核心闭环不依赖真实 LLM | 后续可替换为 Capture Parser Agent |
| 2026-05-16 | Capture 创建后同步生成 InboxItem | 简化 P1 实现 | 后续异步化时保留接口语义 |
| 2026-05-16 | Inbox confirm 使用行锁并保持幂等 | 防止重复点击或并发确认生成重复 Task / Goal | 后续接入请求幂等键时可继续复用 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-16 | 新增 Capture / Inbox 迭代文档 | `docs/iterations/2026-05-16-p1-capture-inbox.md` | 本文件 |
| 2026-05-16 | 新增 Capture / Inbox 模型和 migration | `app/models/capture.py`、`app/models/inbox.py`、`alembic/versions/20260516_0002_capture_inbox.py` | P1 文本输入闭环 |
| 2026-05-16 | 新增 rule parser 和 service | `app/services/capture_parser.py`、`app/services/capture_service.py`、`app/services/inbox_service.py` | 不接真实 LLM |
| 2026-05-16 | 新增 Capture / Inbox API | `app/api/v1/captures.py`、`app/api/v1/inbox.py` | P1 输入与确认层 |
| 2026-05-16 | 新增 service / API 测试 | `tests/test_capture_inbox_services.py`、`tests/test_capture_inbox_api.py` | 覆盖主路径和状态边界 |
| 2026-05-16 | 优化 confirm 幂等和 Inbox 全状态查询 | `app/services/inbox_service.py`、`app/api/v1/inbox.py` | 避免重复生成正式对象，支持 `include_all=true` |

---

## 12. 验证结果

开发完成后填写。

### 已验证

- [x] `python -m unittest discover -s tests`
- [x] `python -m compileall app tests scripts`
- [x] `alembic upgrade head --sql`
- [x] `git diff --check`

### 未验证

- [ ] `alembic upgrade head` 真实连接本地 PostgreSQL 未执行；权限确认两次超时。

### 已知问题

- P1 使用 rule parser，解析质量只服务闭环验证，后续需要替换为 Capture Parser Agent / LLM adapter。

---

## 13. 后续迭代建议

- Today / DailyPlan 基础调度。
- Capture Parser mock Agent -> LLM adapter。
- Task Breakdown mock Agent。
