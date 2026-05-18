# Planner Eval Golden Baseline

Planner eval 是 Chronos AI 编排能力的离线质量尺子。它不替代单元测试和 smoke，但用于回答一个更产品化的问题：

```text
这次改 planner / prompt / provider 后，Today 的执行编排是否还保护了核心产品承诺？
```

当前 golden baseline：

- Policy manifest: [p2-planning-engine-eval-v8.json](./p2-planning-engine-eval-v8.json)
- Evaluator version: `p2-planning-engine-eval-v8`
- Required scenario count: `13`
- Check script: `scripts/check_planner_eval_policy.py`

---

## 使用方式

生成一次 planner eval JSONL：

```bash
uv run python scripts/evaluate_planning_engine.py --run-id policy-check --jsonl-output /tmp/chronos-planner-policy.jsonl
```

检查是否符合当前 golden baseline：

```bash
uv run python scripts/check_planner_eval_policy.py /tmp/chronos-planner-policy.jsonl
```

也可以通过统一验证入口运行：

```bash
uv run python scripts/verify_local.py --planner-eval-policy
```

---

## 判定规则

`regressed` 必须阻断后续发布或真实 provider 验收：

- eval run 本身不是 `ok`
- required scenario 缺失
- required scenario 失败
- required details / item signal 字段缺失

`changed` 不是自动失败，但必须显式记录并更新 policy 或验收结论：

- evaluator version 变化
- 新增 scenario 但 policy 尚未纳入
- compare 结果中排序、容量、risk、prompt checksum、score signal 发生变化

`ok` 表示当前 JSONL 至少满足本 baseline 的结构和场景通过要求。

---

## 维护原则

- 不把 policy check 放入默认 CI / `verify_local`，避免日常开发被离线评估节奏绑死。
- 涉及 planner 权重、Daily Planner prompt、真实 provider adapter 或 fallback 策略时，必须手动运行 policy check。
- 当新增 scenario 或升级 evaluator version 时，必须同步更新 policy manifest 和本说明。
- policy manifest 只记录验收规则，不记录真实用户输入、provider 原始响应或 API key。
