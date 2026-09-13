# Contributing

Contributions that improve deterministic correctness, evidence discipline, portability, documentation and fictional test coverage are welcome.

## Ground rules

- Use fictional or irreversibly anonymized examples only.
- Never add customer data, credentials or private system details.
- Preserve the distinction between measurement, attribution, hypothesis and verified root cause.
- Do not make production connectivity part of the Community Edition.
- Add regression or adversarial cases for every behavioral change.
- Keep deterministic calculations in code rather than in model instructions.

## Before opening a change

Run:

```bash
python3 skills/oee-loss-analyzer/scripts/run_evals.py --all
python3 mcp/smoke_test.py
```

Explain the problem, the expected behavior and the evidence rule affected by the change.
