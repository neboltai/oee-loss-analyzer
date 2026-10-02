# Indulayer OEE Runtime Bridge

Thin HTTP transport around the existing OEE 0.4.0 deterministic engine.

It does not reimplement OEE calculations.

Endpoints:

- `GET /health/ready`
- `POST /api/v1/analysis-runs`

The POST endpoint requires `Authorization: Bearer <OEE_RUNTIME_TOKEN>`.

Run:

```bash
export OEE_RUNTIME_TOKEN='replace-me'
python3 -m runtime.server --host 127.0.0.1 --port 8081
```

The runtime accepts the product-native canonical OEE JSON contract. Raw MES/ERP normalization remains outside the public Community Edition and must be handled by an explicitly reviewed industrial mapping step.
