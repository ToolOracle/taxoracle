# TaxOracle MCP Server v1.0.0

**Advanced Tax Compliance MCP Server — 12 tools for DAC6/DAC7 reporting, OECD Pillar Two (MinStG), transfer pricing, withholding tax (DBA), USt-Voranmeldung (ELSTER), Gewerbesteuer, Betriebsprüfung, HGB/IFRS, AfA, Forschungszulage.**

Port 12801 | Part of [ToolOracle](https://tooloracle.io) & [FeedOracle](https://feedoracle.io) Infrastructure

## Quick Connect

```bash
# Claude Desktop / Claude Code
claude mcp add taxoracle https://tooloracle.io/tax/mcp

# Or use directly
curl -X POST https://tooloracle.io/tax/mcp/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## 12 Tools

| `dac6_assessment` | Tool 1 |
| `pillar_two_calc` | Tool 2 |
| `transfer_pricing` | Tool 3 |
| `withholding_tax` | Tool 4 |
| `pe_risk_check` | Tool 5 |
| `ust_voranmeldung` | Tool 6 |
| `trade_tax_calc` | Tool 7 |
| `betriebspruefung` | Tool 8 |
| `gaap_ifrs_diff` | Tool 9 |
| `depreciation_calc` | Tool 10 |
| `r_and_d_incentive` | Tool 11 |
| `tax_loss_carryforward` | Tool 12 |

## Endpoints

| Endpoint | URL |
|----------|-----|
| MCP (StreamableHTTP) | `https://tooloracle.io/tax/mcp/` |
| MCP (FeedOracle) | `https://feedoracle.io/tax/mcp/` |
| Health | `https://tooloracle.io/tax/health` |

## Architecture

- **Transport**: StreamableHTTP + SSE (MCP Protocol 2025-03-26)
- **Auth**: x402 micropayments (USDC on Base) + Stripe subscriptions
- **Signing**: ECDSA ES256K — every response cryptographically signed
- **Platform**: Whitelabel MCP Platform v1.0

## Part of the ToolOracle Ecosystem

ToolOracle operates 81+ MCP servers with 824+ tools across:
- **Compliance & Regulation** — DORA, MiCA, NIS2, AMLR, GDPR, EU AI Act
- **Finance & Tax** — CFOCoPilot, TaxOracle, ISO20022Oracle
- **Legal** — LawOracle, LegalTechOracle, ContractOracle
- **Healthcare** — HealthGuard
- **Supply Chain** — SupplyChainOracle
- **Cybersecurity** — CyberShield, DORAOracle, TLPTOracle
- **HR** — HROracle
- **Blockchain** — 13 chains (ETH, BTC, Solana, Arbitrum, etc.)
- **Business Intelligence** — SEO, Leads, Reviews, E-Commerce

## License

Proprietary — © 2026 ToolOracle / FeedOracle. All rights reserved.
Contact: enterprise@feedoracle.io
