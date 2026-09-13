# Lean analysis method

How to move from a number to a countermeasure without skipping the step that
makes the countermeasure work.

## The sequence

```
Measure → Stratify → Pareto → Go and see → Ask why → Test the mechanism → Counter → Standardise
```

Each arrow is a place where analyses usually fail. The engine gets you to
"Pareto" reliably; everything after it needs the shopfloor.

## 1. Stratify before you Pareto

An undifferentiated downtime total hides the pattern. Stratify by: machine,
shift, product/order, operator team (for process differences only, never
appraisal), tool/die, material batch, day of week, time within shift.

The useful question is not "how much downtime" but "downtime concentrated in
what". A loss that is flat across every stratification is a design problem; a
loss that spikes in one stratum is a variation problem, and far easier to fix.

## 2. Pareto on minutes, then on frequency

Two Paretos, two different findings:

- **By minutes** → where the output went. Drives the biggest recovery.
- **By frequency** → where the process is unstable. Drives the most durable fix.

A loss that ranks high on frequency and low on minutes is the classic
micro-stop signature: cheap individually, corrosive in aggregate, and the one
most likely to be missing from the log entirely.

## 3. Genchi genbutsu before hypothesis

Do not build a causal story from the data alone. The data says *when* and *how
long*; it rarely says *why*. Before proposing a cause, name what somebody would
have to observe at the machine to confirm or kill it. If the analysis cannot
name that observation, the hypothesis is not yet testable — say so.

## 4. Five Why, honestly

Five Why is only valid when each step is verifiable:

```
Output dropped 12 %            ← measured
because the press stopped 53 min  ← measured, 2 events
because hydraulic pressure dropped ← observed in the alarm log (evidence)
because ...                        ← NOT in the data → this is where the analysis stops
```

Stop the chain at the last verifiable link and say what the next link needs.
A five-level chain built on three levels of evidence is a story, not an analysis.
Two verified links beat five invented ones.

Watch for the two standard failure modes: the chain that ends at "operator
error" (that is a starting point, not a root cause — why did the process allow
it?), and the chain that ends at "no budget" (that is a constraint, not a cause).

## 5. Ishikawa as a checklist, not a conclusion

Use the 6M — Machine, Method, Material, Manpower, Measurement, Milieu — to check
whether the hypothesis space has been explored, especially **Measurement**:
a large share of OEE "losses" are measurement artefacts (wrong ideal cycle time,
unlogged micro-stops, rework counted as good). Rule out Measurement before
spending money on Machine.

A populated fishbone is a list of candidates. It carries no evidential weight
until each branch is tested.

## 6. Correlation is not cause

Recurrent traps in shopfloor data:

- **Coincidence in time.** A work order on the day of a breakdown may have caused
  it, prevented a worse one, or be unrelated.
- **Common cause.** Night shift shows more scrap *and* more downtime — most
  likely both follow from the same upstream input, not from each other.
- **Selection effect.** Only stops longer than 3 minutes are logged, so the log
  "shows" that stops are long.
- **Reverse causation.** Slower running does not cause quality problems; running
  slower is often the operator's countermeasure *to* a quality problem.

Required in the report: every correlation is stated as a correlation, with the
observation that would discriminate between the competing explanations.

## 7. PDCA and the size of the first step

Countermeasures are experiments. Each one gets: the hypothesis, the measure that
will move, the expected size of the move, the review date. Anything without
those four is a wish.

Prefer the smallest reversible experiment that discriminates between hypotheses
over the largest plausible fix. A one-shift measurement of hydraulic pressure at
each tool change costs nothing and kills or confirms a hypothesis that a pump
replacement only tests at the price of a pump.

## 8. Where OEE improvement actually comes from

In order of typical yield for the effort, in discrete manufacturing:

1. Making losses visible (fixing the data collection itself)
2. Reducing changeover time (SMED) where the mix is high
3. Eliminating recurring micro-stops
4. Restoring basic conditions — cleaning, lubrication, fastening, autonomous maintenance
5. Preventing the top-3 recurring failure modes
6. Re-qualifying ideal cycle time and removing unnecessary derating
7. Capital replacement

Steps 1 and 4 are almost always under-done and almost always cheapest. An
analysis that jumps straight to step 7 has usually skipped the evidence.
