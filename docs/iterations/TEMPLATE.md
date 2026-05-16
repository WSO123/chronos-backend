# Iteration: <迭代名称>

> 状态：Draft / In Progress / Ready for Dev / Done / Archived  
> 阶段：P1 / P2 / P3 / P4  
> 创建日期：YYYY-MM-DD  
> 负责人：  
> 关联 PR / Issue / Commit：

---

## 1. 迭代摘要

一句话说明本次迭代要解决什么问题。

```text
示例：跑通 P1 的 Task / Light Goal 基础闭环，为 Today 和 Focus 提供可执行任务底座。
```

---

## 2. 背景与目标

### 关联核心文档

勾选本次迭代需要遵守或引用的文档：

- [ ] [Chronos Product Positioning](../chronos-product-positioning.md)
- [ ] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [ ] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [ ] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [ ] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [ ] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [ ] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

说明这个需求从哪里来：

- 产品定位
- 信息架构
- 交互流程
- 用户问题
- 技术债
- 上一轮迭代遗留

### 目标

本次迭代希望达成什么。

- 目标 1
- 目标 2
- 目标 3

### 非目标

明确这次不做什么，避免 scope creep。

- 非目标 1
- 非目标 2
- 非目标 3

---

## 3. 产品约束对齐

### 核心路径

本次迭代服务哪条路径：

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

勾选：

- [ ] Capture
- [ ] Inbox
- [ ] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

说明本次迭代如何符合：

- 轻盈
- 克制
- 可信赖
- 不施压
- 聪明但不炫耀

### 设计护栏

确认是否遵守：

- [ ] 不让 Today 变成复杂驾驶舱
- [ ] 不让 Task Detail 变成信息仓库
- [ ] 不让 Focus 变成控制面板
- [ ] 不让洞察和解释抢走行动感
- [ ] 不让“聪明”压过“可信”

---

## 4. 需求范围

### 功能清单

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
|  |  | Must / Should / Could |  |

### 用户故事

```text
作为 <用户类型>，
我希望 <能力>，
以便 <价值>。
```

### 主要流程

```text
Step 1
-> Step 2
-> Step 3
```

---

## 5. 后端设计

### 影响模块

勾选：

- [ ] API
- [ ] Service
- [ ] Models
- [ ] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [ ] Tests

### 数据模型变更

新增 / 修改 / 删除的模型：

```text
ModelName {
  field
}
```

### 状态机变更

如无变化，写“无”。

```text
state_a -> state_b
```

### 事件变更

新增或使用哪些 `ActivityEvent`：

- EVENT_NAME
- EVENT_NAME

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| GET / POST / PATCH | `/api/v1/...` |  |  |  |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [ ] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

如涉及，说明：

- Agent 名称：
- 输入对象：
- 输出对象：
- Pydantic schema：
- fallback 策略：
- 是否需要用户确认：

### LLM 安全边界

确认：

- [ ] LLM 不直接写业务表
- [ ] LLM 输出经过 schema validation
- [ ] 失败时有 fallback
- [ ] AIJob 状态可查询
- [ ] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [ ] 验收项 1
- [ ] 验收项 2
- [ ] 验收项 3

### 数据验收

- [ ] 关键数据正确落库
- [ ] 状态机流转正确
- [ ] ActivityEvent 正确记录
- [ ] AIJob 状态正确记录

### 体验验收

- [ ] 用户能清楚知道下一步
- [ ] 页面默认信息不过载
- [ ] AI 解释克制可信
- [ ] 核心流程不因 AI 失败阻塞

---

## 8. 测试计划

### 单元测试

- [ ] Service 测试
- [ ] Schema 测试
- [ ] 状态机测试

### API 测试

- [ ] 正常路径
- [ ] 异常路径
- [ ] 权限 / user_id

### 集成测试

- [ ] DB migration
- [ ] Worker / AIJob
- [ ] fallback 路径

### 手动验证

```text
1. ...
2. ...
3. ...
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
|  |  |  |

### 关键取舍

记录本次迭代中做出的重要取舍。

- 取舍 1：
- 取舍 2：

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| YYYY-MM-DD |  |  |  |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| YYYY-MM-DD |  |  |  |

---

## 12. 验证结果

开发完成后填写。

### 已验证

- [ ] 

### 未验证

- [ ] 

### 已知问题

- 问题 1
- 问题 2

---

## 13. 后续迭代建议

- 建议 1
- 建议 2
- 建议 3
