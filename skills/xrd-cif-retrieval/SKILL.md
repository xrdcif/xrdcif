---
name: xrd-cif-retrieval
description: Cross-modal XRD-CIF crystal retrieval Skill. Trigger when the user asks for XRD phase identification, powder diffraction (pXRD) peak interpretation, matching a diffraction pattern to candidate crystal structures, reverse lookup from a CIF structure to its theoretical XRD pattern, checking SUPPORT/CONTRADICT/INSUFFICIENT three-state physical-rule verification evidence, or checking the daily free quota, account balance, and credit purchase link. Uses scripts/xrd_client.py to call the remote retrieval service, returning Top-K candidate structures with traceable evidence, and clearly printing the purchase link and remaining quota when the free allowance is exhausted. Chinese trigger keywords: 鉴定XRD谱、解释衍射峰位、匹配晶体结构、CIF反查理论衍射谱、查剩余额度.
agent_created: true
---

# XRD-CIF Cross-Modal Crystal Retrieval

## Overview

Wraps a remote XRD-CIF cross-modal retrieval service: feed in an X-ray diffraction pattern, get back Top-K candidate crystal structures, each independently cross-checked by textbook-derived physical rules into a three-state verdict (`SUPPORT` / `CONTRADICT` / `INSUFFICIENT`), with traceable evidence. All capabilities are exposed through `scripts/xrd_client.py` on the command line. The service charges per analysis (credits); each account has a daily free allowance, and additional credits must be purchased on the website once the allowance is exhausted.

## When to use

- Phase identification or peak interpretation from an XRD / pXRD pattern.
- Matching a diffraction pattern to candidate crystal structures; requesting a Top-K candidate list.
- Reverse lookup: theoretical XRD pattern from a CIF structure.
- Inspecting the three-state verdicts and per-candidate `verification` / `render` evidence.
- Checking the daily free quota, balance, ledger, or the credit purchase entry.

## Configuration

Read the service base URL and credentials in this priority order; never write the API key into logs, command echoes, or output.

- Base URL: environment variable `XRD_API_BASE`, default `https://xrdcif.com` (public service; override for local development).
- API key: environment variable `XRD_API_KEY`, or `api_key` / `api_base` in `~/.config/xrd-cif/config.json`.
- Language: environment variable `XRD_LANG`, default `en`, sent as the `X-Lang` header on every request.

To obtain an API key: open `https://xrdcif.com`, register, confirm your email, then generate a key under **Account & Credits → Developer** and set it in `XRD_API_KEY` or the config file. With no key, run `doctor` first — the client self-checks connectivity and prints registration guidance; a 401 response includes the same guidance. The purchase link is returned by the server in `quota` and in 402 responses; never hard-code it in the client.

## Workflow

1. Run `python scripts/xrd_client.py doctor` to check connectivity and key validity. If no key is configured, the client prints registration guidance (site URL and key-generation steps) — present that guidance to the user as-is. Do not register on the user's behalf and never fabricate a key.
2. With a key, run `python scripts/xrd_client.py quota` to read the remaining daily free allowance, balance, and purchase link.
3. Build the pattern and run `search`: `simulate` uses a built-in demo structure, `peaks` reads a 2θ / relative-intensity peak table, `xy` reads a continuous pattern. Use `--k` for the candidate count and `--request-id` with a UUID for idempotency.
4. For per-candidate evidence, run `history` to read the `verification` and `render` traces; for structure reverse lookup, run `reverse`.
5. To inspect account details, run `account`.
6. On HTTP 402 (free allowance and balance both exhausted), print the server-provided purchase link and remaining quota verbatim and stop the retrieval. Never fail silently and never fabricate or cache results. Never fabricate results.

## Command reference

| Command | Purpose | Main options |
| --- | --- | --- |
| `doctor` | Check connectivity and key | `--json` `--timeout` |
| `quota` | Daily free allowance and balance | `--json` `--timeout` |
| `search` | Pattern → Top-K candidates | `--pattern-kind` `--structure-id` `--condition` `--peaks-file` `--xy-file` `--k` `--request-id` `--json` |
| `reverse` | CIF → theoretical pattern | `--structure-id` `--k` `--json` |
| `history` | Full result and evidence | `--history-id` `--json` |
| `account` | Account and ledger | `--json` |

Every subcommand supports `--json` for raw JSON; the default is a human-readable summary. `--timeout` sets an explicit timeout in seconds. See `references/api.md` for the full endpoint, field, error-code, and billing specification; see `README.md` for installation, publishing, and purchase flow.

## Billing and compliance boundaries

- The daily free allowance resets at 00:00 UTC, is fixed per day, and does not accumulate or roll over; `billing.credits` marks whether this call consumed paid credits, and `quota.source` marks the source as `daily_free` or `credits`.
- Results contain same-source self-evaluation metrics for retrieval reference and evidence traceability only; they must not be presented as accuracy claims. Self-evaluation metrics are not accuracy claims.
- Payments are handled on the website side (the Paddle merchant credentials stay server-side); this Skill and the client never touch payment credentials. Payment is handled server-side; this Skill never touches payment credentials.

## Resources

- `scripts/xrd_client.py`: pure-standard-library CLI client, run directly, zero third-party dependencies.
- `references/api.md`: full API contract, fields, error codes, and compliance notes.
- `README.md`: installation, key setup, credit purchase, marketplace publishing notes, and honest boundaries.
