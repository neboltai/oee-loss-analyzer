# OEE loss analysis — {machine_id} / {shift} / {date}

**Status:** `{ok | insufficient_evidence | data_error}` — {one line: what that means here}
**Data source:** {MES / ERP / CMMS / historian / CSV / …} | **Period:** {from}–{to} | **Engine:** {version}

> Delete this line and every `{placeholder}` before delivering. Sections that
> have no content are removed, not left empty. Keep the order.

---

## 1. Headline

{One sentence: the OEE, the single largest loss in minutes, and whether its
cause is established or still a hypothesis. No more than 30 words.}

## 2. Metrics

| Metric | Value | World class | Gap |
|---|---|---|---|
| Availability | {a} % | 90.0 % | {±} pt |
| Performance | {p} % | 95.0 % | {±} pt |
| Quality | {q} % | 99.9 % | {±} pt |
| **OEE** | **{oee} %** | **85.0 %** | **{±} pt** |

Planned production time {ppt} min = fully productive {fpt} min + losses {total} min
(availability {al}, performance {pl}, quality {ql}). Cross-check: {ok | MISMATCH}.

{If TEEP was computed: Utilisation {u} %, TEEP {teep} %.}

## 3. Loss Pareto

| # | Bucket | Loss (min) | Share | OEE factor | Six Big Loss | Events | Attributed |
|---|---|---|---|---|---|---|---|
| 1 | {bucket} | {min} | {%} | {factor} | {1–6 or —} | {n} | {yes/no} |

{One sentence naming the primary loss and whether any bucket ties with it.}

## 4. Findings

Repeat this block per significant loss, primary first.

### {problem — quantified, names the asset, no causal claim unless established}

**Cause established:** {yes / no — hypothesis stage} · **Confidence:** {0.xx}

**Evidence** — verifiable records only, each traceable to an id or a field
- {DT-0031 MECH_FAIL 35 min at 14:12}
- {alarm A-317 "Hydraulic pressure low", 20 s before DT-0031}

**Corroboration links** — explicit record-to-event relations only
- {alarm: DT-0031 ↔ A-317; same machine, 20 s apart, family hydraulic}

**Hypotheses** — not established, each with the correlation it rests on
- {Hydraulic pressure loss recurring after tool change (correlates with order boundary SO-9912; correlation only)}

**What would confirm or kill it at the machine**
- {Observation an operator or technician could make on the next shift}

**Recommended next step**
- {Smallest reversible experiment or measurement that discriminates}

## 5. Missing evidence

- {Exactly what is missing, named at record level — not "more data"}

## 6. Data quality flags

| Flag | What it means for this analysis |
|---|---|
| {CODE} | {effect on the conclusions, in one line} |

## 7. Recommended investigation

Ordered, each with owner, measure, expected move and review date.

| # | Action | Owner | Measure that should move | Expected | Review |
|---|---|---|---|---|---|
| 1 | {action} | {role} | {metric} | {size} | {date} |

---

**Machine-readable findings**

```json
[
  {
    "problem": "...",
    "evidence": [],
    "hypothesis": [],
    "recommended_action": [],
    "confidence": 0.82,
    "corroboration": []
  }
]
```

**Method note.** OEE = Availability × Performance × Quality, computed on planned
production time. Losses are ranked in minutes, not in percentage of their own
factor. Thresholds in force: minor stop {n} min, significance {n} %, attribution
floor {n} %, insufficient evidence below {n} %. Findings marked *hypothesis
stage* are not causes; correlation in time is not evidence of causation.
