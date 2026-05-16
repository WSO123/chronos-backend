# Iteration: P1 Frontend API Contract

> 状态：Done
> 阶段：P1
> 创建日期：2026-05-16
> 负责人：Chronos Team
> 关联 PR / Issue / Commit：

---

## 1. 迭代摘要

沉淀 P1 后端到前端的 API Contract / Handoff 文档，把当前可用接口按 Chronos 页面路径和执行闭环整理，减少后续前端联调中的口径偏差。

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

P1 后端主链路已经具备基础能力，前端下一步需要知道每个页面该调用哪些接口、哪些字段可以信任、哪些入口只是未来阶段占位。仅依赖 Swagger 不足以体现 Chronos 的信息架构和产品约束，所以需要一份按页面和用户路径组织的 handoff 文档。

### 目标

- 按页面整理 P1 API。
- 明确全局 header、错误格式、数据格式和 enum 使用。
- 标注 P1 Ready、Backend Ready 但 P2 UI、以及暂不应依赖的能力。
- 给出推荐前端调用流程和本地验收命令。

### 非目标

- 不新增或修改 API。
- 不替代 OpenAPI / Swagger。
- 不做前端组件设计。
- 不承诺 P2/P3/P4 能力已经可用。

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

这份 API Contract 的重点不是暴露全部技术细节，而是让前端围绕“今天到底先做什么、怎么进入执行、怎么复盘”建立清晰对接路径。文档刻意区分用户可见信息和调试信息，避免把 AIJob、raw output、解释字段推到主界面。

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
| Frontend API Contract | 按页面和主路径整理接口 | Must | P1 handoff |
| Global Contract | Header、错误格式、数据格式 | Must | 避免联调分歧 |
| Phase Boundary | 标注 P1/P2/P3/P4 不可依赖能力 | Must | 防 scope creep |
| Local Validation | 引用 demo seed / smoke 命令 | Must | 支持开发验收 |

### 用户故事

```text
作为 Chronos 前端开发者，
我希望按照页面路径查看后端接口契约，
以便不用在 Swagger 和产品文档之间反复猜测字段用途。
```

### 主要流程

```text
阅读全局约定
-> 按页面查接口
-> 按推荐调用流程接入
-> 用 demo seed / smoke 验证主链路
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

### 事件变更

无。

### API 变更

无新增 API。本迭代仅记录当前 API contract。

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 rule/fallback Agent 说明
- [ ] 新增真实 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

无新增 Agent。文档明确 P1 只使用 rule/mock 的 capture parser、today planner、task breakdown 和 daily report，不接真实 LLM。

### LLM 安全边界

- [x] LLM / rule 输出不直接暴露为主界面复杂信息
- [x] AIJob 作为状态底座，不作为 P1 用户主页面
- [x] 用户仍通过 Inbox、Task Detail、Focus actions 保留修正权

---

## 7. 验收标准

### 功能验收

- [x] 文档覆盖 P1 主路径页面。
- [x] 文档列出当前所有 P1 前端需要的主要 endpoint。
- [x] 文档区分 P1 Ready 与未来阶段能力。
- [x] 文档引用本地 seed / smoke 验收命令。

### 数据验收

- [x] 字段名与当前 `app/schemas` 对齐。
- [x] 路径与当前 `app/api/v1` routes 对齐。
- [x] 错误格式与 `app/api/errors.py` 对齐。

### 体验验收

- [x] 前端可以按页面路径查接口。
- [x] 文档提醒哪些字段不要直接用户可见。
- [x] 文档不鼓励 P1 做复杂驾驶舱、信息仓库或控制面板。

---

## 8. 测试计划

### 静态验证

- [x] `git diff --check`
- [x] 人工对照 `app/api/v1` 与 `app/schemas`

### 自动化测试

- [x] `python -m unittest discover -s tests`
- [x] `python -m compileall app tests scripts`

---

## 9. Review 记录

- API Contract 使用页面视角组织，而不是后端模块视角。
- 明确 `X-User-Id`、错误格式、日期格式和 enum 格式，降低前端联调成本。
- 对 Goals、AIJob 等已存在但非 P1 主界面的能力做了边界标注。
- 对 P2/P3/P4 能力明确写入“不要依赖”，避免前端提前绑定不存在的接口。
