# Toyota Production System — the frame around the numbers

OEE is a measurement. TPS is the reason the measurement matters and the guard
against the ways OEE goes wrong when used alone.

## The two pillars

**Jidoka** — automation with a human touch. The process stops itself when
something abnormal happens, so defects are not passed on and the abnormality
becomes visible. Consequence for this analysis: a stop is not automatically a
loss to be eliminated. A line that stops on detection is doing its job; a line
that runs through a defect posts a better Availability and a worse business
outcome. Never recommend suppressing a stop signal to improve OEE.

**Just-in-Time** — make only what is needed, when it is needed, in the quantity
needed. Consequence: producing to fill an OEE number is overproduction, the
worst of the seven wastes, because it hides all the others. `NO_ORDER` downtime
on a non-constraint machine is a correct outcome, not a loss to fix.

## Muda, Mura, Muri

- **Muda** (waste) — the seven wastes: overproduction, waiting, transport,
  over-processing, inventory, motion, defects. OEE sees roughly three of them:
  waiting (availability), over-processing and reduced speed (performance),
  defects (quality). The other four are invisible to OEE, which is why an OEE
  report is never a complete improvement plan.
- **Mura** (unevenness) — variation in demand, sequence, mix. Mura usually
  *causes* the muda that OEE measures. Changeover losses on a high-mix line are a
  mura symptom; SMED treats the symptom, levelling (heijunka) treats the cause.
- **Muri** (overburden) — pushing people or equipment past sustainable limits.
  Chasing OEE typically creates muri: deferred maintenance, skipped cleaning,
  running above qualified speed. A rising OEE with a rising breakdown frequency
  is the signature, and it is worth naming in a report when the data shows it.

## Genchi genbutsu — go and see

The dataset is a shadow of the process, never the process. Every finding should
carry the observation that would confirm it at the machine. If an analysis
produces no reason to walk to the machine, it has probably produced no finding.

## Standardised work

Improvement is only measurable against a standard. Before attributing a loss to
"the operator", ask whether a standard exists, whether it is current, and whether
it is followed — in that order. An absent standard is a management gap, not a
people problem. This is the discipline behind the "never attribute a loss to a
named person" rule in `business-rules.md`.

## Kaizen and the constraint

Small, continuous, evidence-based change beats infrequent large change — but
only when applied at the constraint. Improving OEE on a non-bottleneck machine
produces inventory, not throughput, and often looks excellent on the dashboard.
Before recommending action, ask whether the analysed asset is the constraint; if
that is unknown, say so and put it first on the investigation list.

## Respect for people

The data-collection system is operated by the people the data describes. An OEE
programme used for appraisal produces cleaner-looking data and dirtier reality:
stops disappear from the log, rework is counted as good, cycle times drift. This
is a measurement risk, not only an ethical one — and a plausible explanation for
a suspiciously flawless dataset, which the analysis is allowed to name.

## The five S as a prerequisite

Sort, set in order, shine, standardise, sustain. "Shine" is inspection: most
early-stage breakdowns and micro-stops trace to basic conditions — dirt,
looseness, lack of lubrication. Where basic conditions are not restored, failure
data is noise. This is why "restore basic conditions" ranks so high in
`lean-analysis-method.md` §8.

## What this means operationally for the analyst

1. A stop for a good reason (jidoka, no demand on a non-constraint) is not a loss
   to eliminate — classify it, do not crusade against it.
2. Ask what the loss is a symptom of one level up — usually mura or absent
   standards — before proposing an equipment fix.
3. Prefer making the loss visible to explaining it away.
4. Put the observation to be made at the machine into every finding.
5. Never recommend a countermeasure that raises the metric while degrading the
   process.
