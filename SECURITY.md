# Security policy

## Community Edition boundary

The bundled MCP server is limited to fictional local mock data. It contains no production connector, authentication flow or secret-management mechanism.

Do not commit:

- credentials, tokens, certificates or `.env` files;
- customer, employee or supplier data;
- identifiable plant, machine or production records;
- private endpoints or network topology;
- customer-specific mappings or commercial integration code.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to **contact@nebolt.ai**. Include the affected version, reproduction steps and potential impact. Do not publish exploitable details before a fix or mitigation is available.

This project is an analysis toolkit and is not a certified safety, quality or production-control system. Validate its outputs with qualified personnel before operational use.
