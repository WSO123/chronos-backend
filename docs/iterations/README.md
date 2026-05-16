# Chronos Iteration Docs

> 本目录用于沉淀每次需求迭代的设计、决策、范围和验收结果。  
> 目标是让 Chronos 的每一次产品和后端变化都可追踪、可复盘、可回溯到产品原则。

---

## 1. 使用原则

每一次进入开发的需求迭代，都必须在本目录新增一份迭代文档。

推荐命名：

```text
YYYY-MM-DD-iteration-name.md
```

示例：

```text
2026-05-16-p1-task-goal-foundation.md
2026-05-20-p1-capture-inbox-flow.md
2026-05-24-p1-today-daily-plan.md
```

---

## 2. 什么时候需要写迭代文档

以下情况必须写：

- 新增一个产品功能或业务模块
- 修改核心交互路径
- 修改数据模型或状态机
- 新增、删除或修改 API
- 接入新的 AI Agent / LLM 能力
- 修改 P1/P2/P3/P4 分期边界
- 对已有需求做较大范围调整

以下情况可以不写独立文档：

- 纯 typo 修复
- 小范围代码重构且不改变行为
- 只调整格式、lint、依赖锁文件

---

## 3. 迭代文档必须回答的问题

每份迭代文档至少要说明：

- 为什么做这个迭代？
- 这个迭代服务 Chronos 哪条核心路径？
- 它是否符合产品定位和产品人格？
- P1/P2/P3/P4 属于哪一阶段？
- 用户故事是什么？如果是纯后端 / 架构迭代，也至少要写开发者故事或系统故事。
- 哪些内容明确不做？
- 影响哪些页面、API、数据模型、事件和 AI Agent？
- 如何验收？
- 有哪些风险和后续待办？

---

## 4. 推荐工作流

1. 从 [TEMPLATE.md](./TEMPLATE.md) 复制一份新文档。
2. 按日期和迭代名称命名。
3. 在开发前完成 `背景`、`用户故事`、`范围`、`后端设计`、`验收标准`。
4. 开发过程中持续更新 `决策记录` 和 `变更记录`。
5. 开发完成后补充 `验证结果`、`遗留问题`、`后续迭代建议`。

---

## 5. 与核心文档的关系

迭代文档必须尽量引用以下核心文档中的约束：

- [Chronos Product Positioning](../chronos-product-positioning.md)
- [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [Chronos Competitive Analysis](../chronos-competitive-analysis.md)
- [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

---

## 6. 一句话规范

```text
任何进入开发的需求，都要有一份可追踪的迭代文档；
任何迭代文档，都要能解释它如何服务 Chronos 的执行闭环。
```
