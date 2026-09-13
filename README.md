# OEE Loss Analyzer — Community Edition

Open, locally executable plugin for deterministic OEE calculation and evidence-gated manufacturing loss analysis.

The Community Edition helps transform a reviewed canonical production dataset into:

- Availability, Performance, Quality and OEE;
- classified manufacturing losses;
- evidence-linked findings;
- explicit uncertainty and missing-evidence statements;
- a structured Markdown or JSON report.

It does not connect to a production MES, ERP, SQL database or customer system. The included MCP server is a local demonstration using fictional data only.

## Why this project exists

OEE arithmetic is simple. Reliable interpretation is not.

This project separates:

1. deterministic validation and calculation;
2. loss classification;
3. corroboration between related records;
4. supported claims and hypotheses that still require investigation.

An alarm or maintenance record somewhere in the same period is not sufficient corroboration. Records must match on relevant dimensions such as equipment, time window, component or event family.

## Community Edition scope

Included:

- OpenAI/Codex and Claude plugin manifests;
- reusable OEE analysis Skill;
- deterministic Python engine;
- canonical JSON schemas;
- evidence-gated corroboration logic;
- 55 fictional regression and adversarial cases;
- local mock MCP server exposing six tools;
- example runtime configuration and report template.

Not included:

- production MES, ERP, SQL, API or file-system connectors;
- customer-specific mappings or rules;
- authentication, authorization or secrets management;
- hosted SaaS operation, monitoring or support;

Production integrations and hosted deployments can be assessed through selected industrial pilot projects: [nebolt.ai/oee-loss-analyzer](https://nebolt.ai/oee-loss-analyzer/).

## Repository structure

```text
.
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
├── .mcp.json
├── agents/
├── examples/
├── mcp/
└── skills/
    └── oee-loss-analyzer/
        ├── SKILL.md
        ├── agents/openai.yaml
        ├── assets/
        ├── references/
        ├── scripts/
        └── tests/
```

## Quick start

Requirements:

- Python 3.9 or later;
- no third-party Python dependency for the deterministic engine and bundled mock MCP.

Validate the fictional example:

```bash
python3 skills/oee-loss-analyzer/scripts/validate.py examples/dataset.example.json
```

Generate an analysis report:

```bash
python3 skills/oee-loss-analyzer/scripts/analyse.py examples/dataset.example.json --report
```

Run the full deterministic evaluation suite:

```bash
python3 skills/oee-loss-analyzer/scripts/run_evals.py --all
```

Run the MCP smoke test:

```bash
python3 mcp/smoke_test.py
```

The MCP server can then be started locally with:

```bash
python3 mcp/server.py
```

The bundled MCP reads only the fictional JSON records under `mcp/mock_data/`. It cannot reach external industrial systems.

## Input contract

The deterministic engine consumes canonical JSON. At minimum, a dataset must contain:

- planned production time;
- downtime;
- ideal cycle time;
- total count;
- exactly one of `good_count` or `reject_count`.

Raw CSV, Excel, PDF, image and system exports must first be normalized and reviewed. The Community Edition provides guidance for that step, but no production-ready raw-input parser.

## Evidence discipline

Each finding contains traceable evidence, explicit hypotheses, recommended
actions and structured corroboration matches. A `cause_claimed` flag only
means that the encoded evidence gate passed; it must not be presented as a
completed 5 Why, Ishikawa or verified root-cause investigation.

The project reports a deterministic `confidence` score based on evidence
coverage and data completeness. It is a workflow indicator, not a statistically
calibrated probability.

## Evaluation

The repository contains 55 fictional deterministic cases covering:

- valid and invalid OEE inputs;
- missing and contradictory quantities;
- downtime and quality loss patterns;
- unrelated alarms or maintenance records;
- temporal, equipment, component and event-family mismatches;
- insufficient evidence and causal overclaiming.

A complete pass confirms that the implementation satisfies the encoded regression contract. It does not demonstrate perfect performance on real factory data. Real-world validation requires anonymized external cases, expert review and a protected holdout set.

## Security and data

Do not add production credentials, customer data or identifiable plant information to this repository. See [SECURITY.md](SECURITY.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Released under the [MIT License](LICENSE).
