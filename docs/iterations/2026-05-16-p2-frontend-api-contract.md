# Iteration: P2 Frontend API Contract

日期：2026-05-16
阶段：P2 目标与洞察增强
状态：Implemented

## 1. 背景

P2 已经补齐 Today Strategy / Insights Preview、Task Priority / Dependency、Goals Home / Detail / Timeline、Weekly / Monthly Report、Insight Detail、Me Insights Overview。若继续只看 P1 合同，后续前端或后端迭代容易漏掉 P2 已可用能力。

## 2. 目标

- 新增 P2 前端 API 合同总览文档。
- 把 P2 Ready 接口集中列出。
- 明确 P2 前端展示约束。
- 标记 P2 仍不可依赖的 P3/P4 能力。

## 3. 非目标

- 不改业务代码。
- 不新增 API。
- 不重新定义 P1 主闭环。

## 4. 新增文档

| 文件 | 说明 |
| --- | --- |
| `docs/chronos-p2-frontend-api-contract.md` | P2 前端 API 合同总览 |

## 5. 覆盖范围

- Today Insights Preview
- Strategy Detail
- Task Priority Adjustment
- Task Dependencies
- Goals Home
- Goal Detail
- Goal Progress Timeline
- Weekly Report
- Monthly Report
- Insight Detail
- Me Insights Overview

## 6. 验收标准

- [x] P2 已完成接口集中列出。
- [x] 每组接口有前端展示约束。
- [x] 明确 P2 仍不依赖 Energy / Social / Calendar / Email / Health / Notification / 真实 LLM。
- [x] Backend Architecture 和 P1 Contract 已加入引用。

## 7. 后续

- P2 API smoke 覆盖扩展。
- P2 文档一致性 review 与修正。
