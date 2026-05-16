# Iteration: P3 Provider Adapter Fake

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Calendar / Email connector 增加 provider adapter 协议和 fake provider，使 worker 能从 provider 层获取规范化外部 item，再沿用 ExternalCaptureImport 进入 Capture / Inbox。

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

上一轮已完成 connector worker placeholder，但 worker 只能消费调用方显式传入的规范化 item。后续真实 Google Calendar / Gmail adapter 接入前，需要先固定 provider adapter 接口，并用 fake provider 完整验证 `provider -> worker -> ExternalCaptureImport -> Capture -> Inbox` 的链路。

### 目标

- 新增 provider adapter 协议和 registry。
- 为 Calendar / Email 支持 fake provider adapter。
- `sync_connection(items=null)` 时通过 provider adapter 获取 item。
- fake provider 从 `DataSourceConnection.connection_metadata.fake_items` 读取测试条目。

### 非目标

- 不接真实 Google Calendar / Gmail / Outlook API。
- 不保存 OAuth token。
- 不实现 provider 失败重试、限流、分页拉取。
- 不改变 Capture / Inbox 用户确认链路。

---

## 3. 产品约束对齐

### 核心路径

```text
Fake Provider -> Worker -> Capture -> Inbox -> Task Detail Source Context
```

- [x] Capture
- [x] Inbox
- [ ] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

本轮仍然把复杂 provider 逻辑藏在后端，只让用户看到可确认的 Inbox 候选项。fake provider 不伪装成真实集成，避免“聪明”压过“可信”。

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
| Provider adapter protocol | 固定 provider fetch 接口 | Must | Calendar / Email |
| Fake provider registry | 当前 provider 均注册 fake adapter | Must | 不接真实 API |
| Metadata fake items | 从 connection metadata 读取 fake item | Must | 可测试 |
| Worker provider fetch | `items=null` 时走 provider | Must | 显式 `items=[]` 不拉取 |

### 用户故事

```text
作为后续 connector 开发者，
我希望有清晰的 provider adapter 接口，
以便我接入真实 Google Calendar / Gmail 时只替换 provider 拉取逻辑。
```

```text
作为 Chronos 用户，
我希望外部来源同步后仍先进入 Inbox 等我确认，
以便系统不会擅自把日历或邮件变成任务压力。
```

```text
作为后端系统，
我希望 fake provider 也走真实导入链路，
以便在没有第三方 API 的情况下验证完整 P3 数据路径。
```

### 主要流程

```text
DataSourceConnection.connection_metadata.fake_items
-> FakeDataSourceProviderAdapter.fetch_items
-> DataSourceSyncService.sync_connection(items=null)
-> ExternalCaptureImport
-> Capture / Inbox
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [ ] Schemas
- [x] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests
- [x] Providers

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

复用：

- `DATA_SOURCE_SYNCED`
- `DATA_SOURCE_SYNC_SKIPPED`
- `EXTERNAL_CAPTURE_IMPORTED`

`DATA_SOURCE_SYNCED` payload 新增：

- `fetched_from_provider`
- `provider_mode`

### API 变更

无前端 API 变更。内部 worker 语义调整：

| Task | 输入 | 行为 |
| --- | --- | --- |
| `data_source.sync_connection` | `items=null` | 使用 provider adapter 拉取 |
| `data_source.sync_connection` | `items=[]` | 显式空结果，不拉取 provider |
| `data_source.sync_connection` | `items=[...]` | 使用调用方传入 item |

Fake metadata:

```json
{
  "connection_metadata": {
    "fake_items": [
      {
        "external_item_id": "fake-calendar-1",
        "title": "完成项目复盘",
        "body": "整理会议结论"
      }
    ],
    "fake_next_cursor": "fake-cursor-2"
  }
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

说明：本轮是非 AI provider adapter，不创建 AIJob。

---

## 7. 验收标准

### 功能验收

- [x] fake calendar provider 能产出规范化 calendar item。
- [x] fake email provider 能产出规范化 email item。
- [x] worker 在 `items=null` 时走 provider adapter。
- [x] worker 在显式传 `items=[]` 时不走 provider adapter。
- [x] fake provider 结果仍进入 Capture / Inbox。

### 数据验收

- [x] `fake_next_cursor` 可更新 `sync_cursor`。
- [x] `ExternalCaptureImport.external_payload.provider_mode=fake`。
- [x] 同步事件记录 `fetched_from_provider=true` 和 `provider_mode=fake`。

### 体验验收

- [x] 不引入真实第三方承诺。
- [x] 不绕过 Inbox 用户确认。
- [x] 不改变 Today / Task Detail 的轻量边界。

---

## 8. 测试计划

### 单元测试

- [x] provider registry 返回 Calendar / Email adapter。
- [x] fake provider metadata item 可导入。
- [x] cursor 可从 fake provider 返回并落到 connection。

### Worker 测试

- [x] 单连接 worker 可通过 fake provider 导入。
- [x] ready connections worker 可处理 Calendar / Email fake provider。

### 集成测试

- [ ] DB migration：本轮无 migration。
- [ ] 真实 provider：本轮不涉及。

### 手动验证

```text
1. 创建 calendar/email connection，并写入 fake_items。
2. 调用 sync_connection(items=null)。
3. 检查 ExternalCaptureImport / Capture / Inbox。
4. 检查 sync_cursor / DATA_SOURCE_SYNCED payload。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| fake provider 被误认为真实接入 | 产品预期错位 | 文档明确 provider_mode=fake |
| provider adapter 依赖 service 形成反向耦合 | 后续难替换 | provider 模块只依赖 model/enums |
| fake item 过度模拟真实 provider | 早期复杂化 | 只支持最小规范化字段 |

### 关键取舍

- 取舍 1：provider adapter 放在 `app/providers`，不依赖业务 service。
- 取舍 2：fake provider 从 connection metadata 读取数据，不新增表。
- 取舍 3：`items=null` 才触发 provider，保留显式空同步语义。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Provider adapter 先做 fake 实现 | 避免真实 OAuth 阻塞后端链路验证 | 后续真实 provider 复用协议 |
| 2026-05-17 | `items=null` 触发 provider | 区分“未传 item”和“明确没有 item” | worker 语义更清晰 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 provider 协议和 fake adapter | `app/providers/data_sources.py` | Calendar / Email |
| 2026-05-17 | 接入 sync service | `app/services/data_source_sync_service.py` | provider fetch |
| 2026-05-17 | 调整 worker 参数语义 | `app/workers/tasks.py` | `items=null` 走 provider |
| 2026-05-17 | 补测试 | `tests/test_data_source_sync_service.py` | provider + worker |
| 2026-05-17 | 更新文档 | P3 contract / architecture | fake provider 说明 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_data_source_sync_service`
- [x] `uv run python -m unittest tests.test_data_source_sync_service tests.test_external_capture_import_services tests.test_external_capture_import_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

### 未验证

- [ ] 真实 Google Calendar / Gmail / Outlook provider。
- [ ] OAuth token refresh。
- [ ] provider 分页 / 失败重试 / 限流。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- Calendar real provider adapter skeleton。
- Email real provider adapter skeleton。
- DataSource SyncRun 观测模型或 retry 策略。
