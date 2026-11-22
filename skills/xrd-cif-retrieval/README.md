# XRD-CIF Retrieval Skill

A standard-library-only CLI Skill for XRD-to-CIF cross-modal crystal retrieval. Given a powder XRD diffraction pattern, it returns Top-K candidate crystal structures, each independently cross-checked by textbook-derived physical rules into a three-state verdict (`SUPPORT` / `CONTRADICT` / `INSUFFICIENT`), with inspectable `verification` and `render` evidence. The client uses only the Python standard library — zero third-party dependencies.

The retrieval service is provided by [xrdcif.com](https://xrdcif.com); this Skill calls its public API through the CLI client.

## Capabilities

| Command | Purpose |
|---|---|
| `doctor` | Check service connectivity and API key |
| `quota` | Show the daily free allowance, paid balance, and purchase link |
| `search` | Diffraction pattern → Top-K candidates (`simulate` / `peaks` / `xy` inputs) |
| `reverse` | CIF structure → theoretical diffraction pattern |
| `history` | Full result and per-candidate `verification` / `render` evidence |
| `account` | Account and ledger summary |

## Layout

```
xrd-cif-retrieval/
├── SKILL.md                 # Skill entry: frontmatter and workflow instructions
├── README.md                # This file
├── scripts/
│   └── xrd_client.py        # Pure-standard-library CLI client (urllib, no dependencies)
└── references/
    └── api.md               # API contract, fields, error codes, compliance notes
```

## Installation

Place this directory into your agent's user-level skills directory, keeping the folder name `xrd-cif-retrieval`. For WorkBuddy:

```
~/.workbuddy/skills/xrd-cif-retrieval/SKILL.md
~/.workbuddy/skills/xrd-cif-retrieval/scripts/xrd_client.py
~/.workbuddy/skills/xrd-cif-retrieval/references/api.md
```

Other platforms use their own documented user-level skills paths. No build step is needed — run the client with the system Python.

You can also install via the skills CLI:

```bash
npx skills add https://github.com/xrdcif/xrdcif --skill xrd-cif-retrieval
```

## Configuration

Configuration is read in this priority order: environment variables > config file > defaults.

| Item | Description |
|---|---|
| `XRD_API_BASE` | Service base URL, default `https://xrdcif.com`; override for local development |
| `XRD_API_KEY` | API key |
| `XRD_LANG` | Request language, default `en`, sent in the `X-Lang` header |
| `~/.config/xrd-cif/config.json` | `{"api_key": "...", "api_base": "..."}` |

To get an API key: register at [xrdcif.com](https://xrdcif.com), confirm your email, then generate a key under **Account & Credits → Developer** and set it in `XRD_API_KEY` or the config file above.

With no key set, run `python scripts/xrd_client.py doctor` first: the client self-checks connectivity and prints registration guidance. Any endpoint requiring authentication returns 401 with the same guidance.

The API key is passed only in the `X-API-Key` request header (the server also accepts `Authorization: Bearer`); it never appears in a URL, log, or any output. The purchase link `buy_url` is returned by the server in `quota` and in 402 responses — the client never hard-codes a purchase URL.

## Credits

- Each account gets a fixed daily free allowance, reset on a UTC day boundary; it does not accumulate or roll over.
- Billing order: the daily free allowance is consumed first, then the paid credit balance.
- `quota` shows the current `free_remaining`, `balance`, and `buy_url` at any time.
- When both the free allowance and balance are 0, `search` returns HTTP 402 (`InsufficientCredits`); the client clearly prints the purchase link and remaining quota, exits non-zero, and states explicitly that no result was fabricated.
- Purchases are completed on the website (Paddle merchant account); this Skill and the client never touch payment credentials.

## Quick start

Run these from the Skill root directory (or point directly at `scripts/xrd_client.py`):

```bash
# Check connectivity and key
python scripts/xrd_client.py doctor

# Daily free allowance, balance, and purchase link
python scripts/xrd_client.py quota

# Built-in demo structure search (simulate / NaCl-rocksalt / clean)
python scripts/xrd_client.py search

# Peak-table mode (2θ and relative intensity)
python scripts/xrd_client.py search --pattern-kind peaks --peaks-file peaks.txt --k 5

# Continuous-pattern mode
python scripts/xrd_client.py search --pattern-kind xy --xy-file pattern.xy --k 5 --json

# CIF structure reverse lookup
python scripts/xrd_client.py reverse --structure-id NaCl-rocksalt --k 3

# Full result and per-candidate evidence (replace HISTORY_ID with a real value)
python scripts/xrd_client.py history --history-id HISTORY_ID

# Account and ledger
python scripts/xrd_client.py account
```

Every subcommand supports `--json` (raw JSON) and `--timeout` (explicit timeout in seconds). See [`references/api.md`](references/api.md) for the full endpoint, field, and error-code reference.

## Boundaries and compliance

- Results contain same-source self-evaluation metrics for retrieval reference and evidence traceability only; **do not cite them as generalization accuracy**.
- The three-state verdicts come from textbook-derived physical rules as an independent cross-check; they are not a guarantee of identification accuracy.
- The candidate library and simulated patterns come from the same physics engine; verify critical conclusions against primary literature or standard databases.
- On exhausted credits the client never fabricates or caches results; on 402 it prints the purchase link and remaining quota clearly.
- The API key is never echoed or written to logs.

This Skill is distributed for research and educational use. Service terms and refund policy are available on the website.
