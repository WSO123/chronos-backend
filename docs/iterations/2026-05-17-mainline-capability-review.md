# Iteration: Mainline Capability Review

> 状态：Done
> 阶段：P1 / P2
> 创建日期：2026-05-17
> 负责人：Codex
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增一份常驻主线能力复盘文档，用来约束后续迭代优先围绕 P1 执行闭环和 P2 核心增强推进，避免继续扩散到 P3/P4、商业化、前端页面或高级 Auth。

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

最近几轮迭代已经把 Inbox confirm、Today refresh、Focus auto-link、Daily Report refresh、Goal dependency next task 等关键状态联动补上。项目需要一份常驻复盘文档，把“当前哪些能力已接近闭环”“哪些只是基础可用”“哪些明确暂缓”写清楚，供后续每轮迭代做偏航检查。

### 目标

- 定义后续功能成熟度评估口径。
- 复盘当前 P1 核心闭环和 P2 主线增强的真实成熟度。
- 明确 P3/P4、商业化、前端页面、高级 Auth 等当前暂缓项。
- 给出下一阶段主线优先级和验证基线。

### 非目标

- 不修改业务代码。
- 不新增 API。
- 不引入新的验收工具。
- 不扩展 P3/P4 能力。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [x] Capture
- [x] Inbox
- [x] Today
- [x] Task Detail
- [x] Focus
- [x] Report
- [x] Me
- [x] Goals
- [x] AI Agent

### 产品人格

- 轻盈：把复盘结论收敛成能力等级和下一步优先级，不写成大型路线图。
- 克制：明确暂缓 P3/P4 和非主线方向。
- 可信赖：用最近提交和已有 API contract 对齐能力成熟度。
- 聪明但不炫耀：AI Agent 只作为 bounded、可解释能力描述，不把 LLM 放成隐藏控制平面。

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
| Mainline capability review | 新增常驻复盘文档 | Must | 指导后续迭代 |
| Maturity levels | 定义 L0-L3 能力成熟度 | Must | 防止只堆接口 |
| Drift guard checklist | 增加每轮防偏航问题 | Must | 避免偏离主线 |
| Architecture index update | 在架构文档入口挂载复盘文档 | Should | 方便查找 |

### 用户故事

```text
作为后续开发者，
我希望能快速判断一个需求是否真的增强了 Chronos 主线闭环，
以便避免把时间花在 P3/P4、商业化或前端页面等当前不重要的方向上。
```

```text
作为产品负责人，
我希望看到当前 P1/P2 能力真实成熟度，
以便决定下一轮应该继续打磨核心闭环，而不是被已有扩展文档带偏。
```

### 主要流程

```text
阅读本轮迭代需求
-> 对照 Mainline Capability Review
-> 判断是否服务 P1/P2 主线
-> 开发 / 验证 / review
-> 更新迭代文档和必要合同
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [ ] Service
- [ ] Models
- [ ] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [ ] Tests
- [x] Docs

### 数据模型变更

无。

### 状态机变更

无。

### API 变更

无。

---

## 6. AI / Agent 设计

无新增 Agent。

本次只固化 AI 主线边界：

- Planning Engine v1 是排序 source of truth。
- LLM Agent 只能做解析、建议、解释和复盘文案。
- 不允许绕过 Inbox 或直接修改核心业务状态。

---

## 7. 验证计划

### 自动化测试

本次为文档变更，不运行业务测试。

### 手动验证

- [x] 对齐架构文档、P1/P2 contract 和最近迭代记录。
- [x] `git diff --check`

### 验收标准

- 新复盘文档能清楚区分 P1/P2 主线、P3/P4 暂缓项和下一阶段优先级。
- 架构文档能跳转到复盘文档。
- 文档不暗示继续做前端、商业化、高级 Auth 或 P3/P4。

---

## 8. 风险与边界

| 风险 | 处理 |
| --- | --- |
| 把已有 P3 文档误读成当前优先级 | 明确 P3/P4 当前暂缓 |
| 过度宣称 AI 已接管决策 | 明确 Planning Engine 是 source of truth |
| 文档变成临时总结 | 放入 `docs/` 根目录并在架构文档入口引用 |

---

## 9. 迭代完成记录

### 实际完成

- 新增 `docs/chronos-mainline-capability-review-2026-05-17.md`。
- 在 `docs/chronos-backend-architecture-v1.md` 关联文档中增加入口。
- 新增本迭代记录。

### 偏航检查

- 未新增 P3/P4 能力。
- 未做商业化、前端页面或高级 Auth。
- 未新增工具链。
- 继续围绕 P1/P2 主线状态一致性和可解释性收敛。

### 后续建议

下一轮优先补一个更完整的主线 smoke，覆盖最近 6 个主线状态联动，防止 `Inbox confirm -> Today refresh -> Task Detail -> Focus -> Daily Report` 后续回退。
