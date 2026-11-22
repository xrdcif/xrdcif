# XRD↔CIF Retrieval Skill

[简体中文](README.zh-CN.md) · [Live service](https://xrdcif.com)

[![skills.sh](https://skills.sh/b/xrdcif/xrdcif)](https://skills.sh/xrdcif/xrdcif)

**Ask your AI agent to identify a crystal phase from a powder XRD pattern — and get ranked CIF candidates with traceable physical-rule evidence, not a black-box guess.**

This is a plug-and-play Skill for [WorkBuddy](https://www.workbuddy.cn/), Claude, and other agents that support the `SKILL.md` convention. It wraps the free XRD↔CIF cross-modal retrieval service at [xrdcif.com](https://xrdcif.com): feed in a diffraction pattern, get back Top-K candidate crystal structures, each independently checked against textbook-derived physical rules and labeled `SUPPORT` / `CONTRADICT` / `INSUFFICIENT`. The client is pure Python standard library — zero dependencies, works offline-to-API on any machine.

> The Skill itself is free and open. It is a client: retrieval, quota, and payment happen on the website side. Free daily credits are granted on signup so you can try it before paying.

---

## Why you might want it

If you work with powder diffraction, you know the drill: match peaks against ICDD/PDF cards, eyeball candidate structures, cross-check lattice parameters by hand. This Skill turns that loop into a single conversation with your agent:

- **Phase identification** — "Here is my 2θ/intensity peak table, what structures could this be?"
- **Peak interpretation** — explain what a given diffraction pattern is consistent with.
- **Reverse lookup** — "Give me the theoretical XRD pattern for this CIF structure."
- **Evidence, not just answers** — every candidate carries a three-state physics check (`SUPPORT` / `CONTRADICT` / `INSUFFICIENT`) plus `verification` and `render` records you can inspect.

It runs inside your agent, so you stay in one workspace instead of switching to a web form.

---

## Quick start (3 steps)

### 1. Install the Skill

**Recommended — one command via the agent-skills CLI** (works with Claude Code, Cursor, Windsurf, and any agent that follows the `SKILL.md` convention):

```bash
npx skills add https://github.com/xrdcif/xrdcif --skill xrd-cif-retrieval
```

**Or install manually.** Copy the `skills/xrd-cif-retrieval/` folder into your agent's user-level skills directory, keeping the folder name:

| Platform | User-level skills directory |
|---|---|
| WorkBuddy | `~/.workbuddy/skills/xrd-cif-retrieval/` |
| Claude / other `SKILL.md` agents | your platform's documented user skills path |

No build step. The client needs only Python 3 (standard library).

### 2. Get a free API key

1. Register at **[https://xrdcif.com](https://xrdcif.com)** (registration grants credits + a daily free allowance).
2. Confirm your email.
3. Open **Account & Credits → Developer**, generate an API key.
4. Export it:

```bash
export XRD_API_KEY=xrdk_xxx          # Windows PowerShell: $env:XRD_API_KEY="xrdk_xxx"
```

### 3. Talk to your agent

Just ask in natural language — e.g. *"Use the XRD-CIF skill to identify this pattern: 31.70 100, 45.45 55, 56.55 20 ..."*. The Skill auto-runs `doctor` and guides you through setup if the key is missing.

Or call the CLI directly from the Skill folder:

```bash
python scripts/xrd_client.py doctor     # self-check (prints registration guidance if no key)
python scripts/xrd_client.py quota      # daily free credits + balance + purchase link
python scripts/xrd_client.py search --k 5
```

---

## What it can do

| Command | Purpose | Notes |
|---|---|---|
| `doctor` | Connectivity + key check | No key → prints registration guidance, no dead-end error |
| `quota` | Daily free allowance, balance, purchase link | Read-only, no charge |
| `search` | Pattern → Top-K CIF candidates | `simulate` / `peaks` / `xy` input modes |
| `reverse` | CIF structure → theoretical pattern | Fast structure lookup |
| `history` | Full result + per-candidate evidence | `verification` / `render` traces |
| `account` | Account, balance, ledger summary | — |

Input modes for `search`:

- `simulate` — built-in demo structure (default `NaCl-rocksalt`), zero setup;
- `peaks` — a 2θ / relative-intensity peak table file (`--peaks-file`);
- `xy` — a continuous pattern file (`--xy-file`).

Every call supports `--json` (raw JSON) and `--timeout`. All failures return non-zero exit codes; the client never silently fails.

---

## Quota & payment

- Signup grants credits plus a **fixed daily free allowance**, reset at 00:00 UTC, non-cumulative.
- Daily free allowance is consumed first, then paid credits.
- When both run out, the service returns **HTTP 402**; the client prints the server-provided purchase link and remaining quota, then stops. **It never fabricates or caches results.**
- Payment is handled on the website via Paddle. The Skill and CLI never touch payment credentials and never hard-code a purchase URL — the link always comes from the server.

---

## Honest boundaries

We would rather tell you upfront than have you find out later:

- **Self-evaluation is same-source.** Candidate library and simulated patterns come from the same physics engine and the same built-in structures. Recall/AUC numbers on the website are regression self-checks, **not generalization accuracy claims** — do not cite them as performance results.
- **Library status.** The service ships a 27-structure built-in demo gallery and 27 measured-pattern references; the full COD dataset integration is in progress. Results are a research aid, not a certified phase-ID authority.
- **Three-state checks are rule-based.** `SUPPORT` / `CONTRADICT` / `INSUFFICIENT` come from textbook-extracted physical rules; they are independent cross-checks, not a guarantee of identification accuracy.
- **Always verify critical results** against primary literature or standard databases before relying on them in published work.

---

## Requirements

- Python 3.x (standard library only — `urllib`, no pip install needed)
- An API key from [xrdcif.com](https://xrdcif.com) (free to register)
- An agent that reads `SKILL.md`, or direct CLI use

## For skill-directory maintainers

This repository follows the layout expected by [skills.sh](https://skills.sh) and the `npx skills` CLI: one skill per folder under `skills/`, each with a `SKILL.md`. The CLI discovers `skills/xrd-cif-retrieval/SKILL.md` automatically; no registry submit form is needed. Directory listings are driven by anonymous install telemetry from `npx skills add`, so appearing on the leaderboard requires users to actually install it.

## Links

- Service & free registration: **[https://xrdcif.com](https://xrdcif.com)**
- Pricing: [https://xrdcif.com/pricing](https://xrdcif.com/pricing)
- API contract: [`skills/xrd-cif-retrieval/references/api.md`](skills/xrd-cif-retrieval/references/api.md)

---

This Skill is distributed for research and educational use. See the service website for terms, refund policy, and privacy.
