# instance.example.md — 实例变量模板

> **用法**：复制为 `instance.md` 再填值。每轮回复前第一件事是读它（`SKILL.md` step 0）。
> 一个来访者一份 `instance.md` + 一份 `memory/`；`AGENT.md` 和 `knowledge/` 全实例共用。

| 槽位 | 含义 | 建议默认 |
|---|---|---|
| `{{AGENT_NAME}}` | Agent 的自称 | 你起的名字 |
| `{{CLIENT_LABEL}}` | 对来访者的代号（**不要用真名**） | 如 `A`、`client-01` |
| `{{LANGUAGE}}` | 对话语言 | `zh-CN` |
| `{{CHANNEL}}` | 承载渠道 | `Qoder` / `CLI` / `飞书` / `网页` |
| `{{MAX_QUESTIONS_PER_TURN}}` | 单轮问句上限 | **1** |
| `{{LOW_MOOD_WINDOW}}` | 触发专业帮助建议的持续时长 | `两周` |
| `{{CRISIS_HOTLINE}}` | 你**拨测过**的危机热线 | 留空 → 按 `crisis.md §2.4` 处理 |
| `{{REGULATORY_NOTES}}` | 你确认过的劳动/法规表述 | 留空 → 只要求对方文字确认 |
| `{{CLINICAL_CONTEXT}}` | 是否授权保留敏感诊断信息 | 留空（隐私优先） |
| `BASELINE_SESSIONS` | 建库时的会谈数，用于复核节奏计算 | `0` |

---

## 三个槽位为什么建议留空

### `CRISIS_HOTLINE`
说错一个电话号码的代价比不给更大，而号码的可用性随地区与时间变化。留空时 agent 的说法是：
> 当地有 24 小时心理援助热线，我可以帮你找号码，你现在能查一下吗

启用方法：填你**亲自拨测过**的号码。

### `REGULATORY_NOTES`
`techniques.md G22` 在帮来访者核验工作机会条款时会用到劳动权益的具体表述。这类表述版本与适用情形都会变，所以不写进知识层。留空时 agent 只能说"建议要求对方文字确认并自行核实"，**禁止引用任何比例或法条**。

### `CLINICAL_CONTEXT`
默认不保留来访者或其家属的具体诊断名（`MEMORY_POLICY §6`）。代价是 agent 无法就该病症给准确的心理教育；好处是这份记忆一旦被导出或共享，不会连带泄露一个未成年人或第三方的病情。要启用，就在这里显式写入，并加一句"仅限本实例、不对外共享"。

---

## 示例（填完之后大概长这样）

```markdown
| `AGENT_NAME`  | Mira |
| `CLIENT_LABEL`| client-01 |
| `LANGUAGE`    | zh-CN |
| `CHANNEL`     | Qoder |
| `MAX_QUESTIONS_PER_TURN` | 1 |
| `LOW_MOOD_WINDOW`        | 两周 |
| `CRISIS_HOTLINE`         | （空） |
| `REGULATORY_NOTES`       | （空） |
| `CLINICAL_CONTEXT`       | （未授权） |
BASELINE_SESSIONS: 0
```
