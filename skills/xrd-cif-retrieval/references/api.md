# XRD-CIF Retrieval Service API Contract (Client Reference)

This file is the complete server-side contract that `scripts/xrd_client.py` depends on, for development and troubleshooting. The server implements this contract; the client only consumes it and never modifies it. All responses are JSON; POST bodies are JSON, GET requests have no body.

## 1. Base URL and configuration

- Base URL: environment variable `XRD_API_BASE`, default `https://xrdcif.com` (override for local development).
- Optional config file: `~/.config/xrd-cif/config.json`, format `{"api_key": "...", "api_base": "..."}`.
- Priority: environment variables > config file > defaults.
- API key: environment variable `XRD_API_KEY`, or the `api_key` field in the config file.
- Language: environment variable `XRD_LANG`, default `en`.

## 2. Authentication and common headers

| Header | Value | Purpose |
| --- | --- | --- |
| `X-API-Key` | API key | Primary authentication method, used by the client |
| `Authorization` | `Bearer <key>` | Equivalent method also accepted by the server |
| `X-Lang` | `XRD_LANG` or default `en` | Must be sent on every request |
| `Content-Type` | `application/json` | POST requests |
| `Accept` | `application/json` | All requests |

Security rule: the API key appears only in request headers, never in a URL, stdout, stderr, or logs. Never log the API key.

## 3. Endpoints

### 3.1 GET /api/v1/quota

Returns the daily free allowance, account balance, and purchase link. No request body.

Example response:

```json
{
  "free_limit": 30,
  "free_used": 2,
  "free_remaining": 28,
  "day_utc": "2026-11-22",
  "balance": 20,
  "currency": "USD",
  "buy_url": "https://xrdcif.com/pricing",
  "plan": "free"
}
```

Fields:

| Field | Meaning |
| --- | --- |
| `free_limit` | Daily free allowance cap |
| `free_used` | Free uses consumed today |
| `free_remaining` | Free uses remaining today |
| `day_utc` | UTC date the allowance belongs to |
| `balance` | Paid analysis-credit balance |
| `currency` | Currency of the balance |
| `buy_url` | Website link for buying credits, returned by the server — the client must never hard-code it |
| `plan` | Current plan identifier |

### 3.2 POST /api/v1/search

Searches a diffraction pattern, returning Top-K candidate structures, the three-state verdict, and billing information.

Request body:

```json
{
  "pattern": {"kind": "simulate", "structure_id": "NaCl-rocksalt", "condition": "clean"},
  "k": 5,
  "request_id": "<uuid>"
}
```

`pattern` supports three `kind` values:

| kind | Structure | Purpose |
| --- | --- | --- |
| `simulate` | `{"kind":"simulate","structure_id":"NaCl-rocksalt","condition":"clean"}` | Generate a pattern from a built-in demo structure |
| `peaks` | `{"kind":"peaks","text":"31.70 1.000\n45.45 0.55\n..."}` | 2θ / relative-intensity peak table text |
| `xy` | `{"kind":"xy","text":"10.00 0.001\n..."}` | Continuous-pattern text |

`k` is the number of candidates to return; `request_id` is the idempotency key — resubmitting the same value returns 409.

Successful response:

```json
{
  "history_id": "...",
  "result": {"decision": "...", "candidates": [], "pattern": {}, "meta": {}},
  "billing": {"credits": 0, "balance_after": 20},
  "quota": {"free_remaining": 3, "source": "daily_free"}
}
```

Fields:

| Field | Meaning |
| --- | --- |
| `history_id` | Result ID, used by the `history` endpoint to retrieve the full result |
| `result.decision` | Three-state verdict (SUPPORT / CONTRADICT / INSUFFICIENT) |
| `result.candidates` | Top-K candidate structures, each with ID, score, and verification info |
| `result.pattern` | Diffraction-pattern input echoed by the server |
| `result.meta` | Retrieval metadata |
| `billing.credits` | Paid credits consumed by this call: 0 = daily free allowance, 1 = paid balance |
| `billing.balance_after` | Balance after billing |
| `quota.free_remaining` | Free uses remaining after billing |
| `quota.source` | Billing source of this call: `daily_free` or `credits` |

### 3.3 POST /api/v1/reverse

Reverse lookup from a CIF structure to its theoretical diffraction pattern, returning match results.

Request body:

```json
{"structure_id": "NaCl-rocksalt", "k": 3}
```

The response is the reverse-lookup match result (JSON); the exact match fields are defined by the server, and the client presents them as a generic structured summary or as raw JSON with `--json`.

### 3.4 GET /api/v1/history/<history_id>

Retrieves the full retrieval result, including each candidate's `verification` evidence and `render` text. The `history_id` comes from the `search` response; the client URL-escapes this path segment.

### 3.5 GET /api/v1/account

Returns account info, balance, and a ledger summary (JSON).

## 4. Error codes

| Status | Type | Meaning | Client handling |
| --- | --- | --- | --- |
| 200 | - | Success | Print summary or raw JSON |
| 401 | `AuthError` | API key missing, invalid, or revoked | Print registration guidance (site URL + key-generation steps), exit non-zero |
| 402 | `InsufficientCredits` | Free allowance exhausted and balance is 0 | Prominently print the purchase link and remaining quota, stop retrieval, exit non-zero |
| 403 | Forbidden / email unverified | Credential lacks access, or the token's account has not confirmed email (`code=email_unverified`) | Report forbidden; on unverified email, guide the user to check their confirmation email or resend it on the website |
| 409 | Conflict | `request_id` already used | Ask the user to change `request_id` and retry |
| 429 | Rate limited | Too many requests | Ask the user to retry later |
| 5xx | Server error | Service failure | Print error details, exit non-zero |
| Local | Network / timeout | Connection failure, timeout, non-JSON response | Friendly message, exit non-zero |

Example 402 response body:

```json
{
  "error": "...",
  "type": "InsufficientCredits",
  "quota": {"free_remaining": 0, "day_utc": "2026-11-22", "source": "credits"},
  "buy_url": "https://xrdcif.com/pricing"
}
```

Client contract: it must recognize 402, clearly print `buy_url` and the remaining quota from `quota`, and return a non-zero exit code. Never fail silently and never fabricate or cache results. Never fabricate results on 402.

## 5. Free allowance and billing rules

- The free allowance resets on a UTC day boundary (field `day_utc`), daily.
- The allowance is fixed at `free_limit`; it does not accumulate or roll over.
- Billing order: consume the daily free allowance first, then the paid balance `balance`.
- `quota.source` marks this call's source as `daily_free` (free) or `credits` (paid).
- `billing.credits` marks whether this call consumed paid credits: 0 = free, 1 = paid.
- When both the free allowance and paid balance are 0, the service returns 402; the user must buy analysis credits at the website pricing page pointed to by `buy_url` before continuing.
- Purchases and payments happen on the website side; the Skill and the client do not handle payment credentials.

## 6. Compliance notes

- Results contain same-source self-evaluation metrics; they are for retrieval reference and evidence traceability only and must not be used as accuracy claims in marketing. Self-evaluation metrics are not accuracy claims.
- The three-state verdicts SUPPORT / CONTRADICT / INSUFFICIENT are independent cross-checks based on physical rules extracted from textbooks; they are not a guarantee of identification accuracy.
- Payments are handled server-side via the Paddle merchant account; this contract and the client never cover payment credentials.
- The client must never echo the API key or write it to logs or error messages.

## 7. Client behavior contract

- Pure Python standard library `urllib`, zero third-party dependencies; run directly with `python xrd_client.py <command>`.
- Explicit timeouts; friendly messages on network errors; every failure path returns a non-zero exit code.
- `--json` outputs raw JSON; the default is a human-readable summary.
- Every request carries `X-Lang`; both GET and POST carry `Accept: application/json`.
