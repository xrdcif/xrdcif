#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI client for the XRD-CIF cross-modal crystal retrieval service.

Uses only the Python standard library (urllib), no third-party dependencies:
    python xrd_client.py <command> [options]

Commands:
    quota    Show the daily free allowance and account balance
    search   Diffraction-pattern search for Top-K candidate structures
    reverse  Reverse lookup from a CIF structure to its theoretical pattern
    history  Read the full result and per-candidate evidence
    account  Show account and ledger summary
    doctor   Check connectivity and whether the API key is valid

Security rule: the API key goes only into request headers, never into stdout,
stderr, or logs. Never print or log the API key.
"""

import argparse
import json
import os
import sys
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Windows consoles may not handle UTF-8 output by default, so force it.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Default to the public service; override with XRD_API_BASE or the config file.
DEFAULT_BASE = "https://xrdcif.com"
# Registration page: where users without a key obtain one.
SITE_URL = (os.environ.get("XRD_SITE_URL") or "https://xrdcif.com").rstrip("/")
# Public connectivity probe (no key required), used by doctor before a key exists.
HEALTH_PATH = "/api/health"
CONFIG_PATH = Path.home() / ".config" / "xrd-cif" / "config.json"
DEFAULT_TIMEOUT = 15.0
MAX_DEPTH = 4

# Exit codes, so external scripts can branch on the result.
EXIT_OK = 0
EXIT_USAGE = 1
EXIT_NETWORK = 2
EXIT_HTTP = 3
EXIT_BAD_RESPONSE = 4
EXIT_402 = 10
EXIT_401 = 11
EXIT_403 = 12
EXIT_409 = 13
EXIT_429 = 14


class UsageError(Exception):
    """Invalid arguments or input file."""


class ApiError(Exception):
    """Server or network error.

    status: HTTP status code; 0 = network/timeout; -1 = response was not valid JSON.
    payload: parsed JSON (may be None).
    message: short user-facing explanation, containing no credentials.
    """

    def __init__(self, status, payload, message):
        super().__init__(message)
        self.status = status
        self.payload = payload
        self.message = message


def load_config():
    """Read base URL, API key, and language.

    Priority: XRD_API_BASE / XRD_API_KEY / XRD_LANG environment variables,
    then api_base / api_key in ~/.config/xrd-cif/config.json,
    then defaults. The returned value contains the key, but no caller may print it.
    """
    api_base = os.environ.get("XRD_API_BASE")
    api_key = os.environ.get("XRD_API_KEY")
    lang = os.environ.get("XRD_LANG") or "en"

    cfg = {}
    if CONFIG_PATH.is_file():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[warning] Config file unreadable, ignored: {type(exc).__name__}", file=sys.stderr)

    if not api_base:
        api_base = cfg.get("api_base") or DEFAULT_BASE
    if not api_key:
        api_key = cfg.get("api_key") or ""

    return {
        "api_base": str(api_base).rstrip("/"),
        "api_key": str(api_key),
        "lang": str(lang),
    }


def parse_json(raw):
    """Parse response text as JSON, returning None on failure."""
    if not raw or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def error_message(payload, status):
    """Extract error / type from an error response, building a credential-free message."""
    if isinstance(payload, dict):
        err = payload.get("error") or payload.get("message")
        if err:
            typ = payload.get("type")
            return f"{err}" + (f" [type={typ}]" if typ else "")
    return f"HTTP {status}"


def open_url(req, timeout):
    """Open a request; bypass the HTTP proxy for loopback addresses.

    The default base URL is 127.0.0.1; if HTTP_PROXY is set, the proxy turns
    local requests into 5xx, so localhost / 127.0.0.1 / ::1 are forced direct.
    Bypass proxies for loopback hosts.
    """
    host = (urllib.parse.urlsplit(req.full_url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def request(method, path, config, body, timeout):
    """Make one HTTP request and return parsed JSON.

    Always sends X-API-Key and X-Lang headers; explicit timeout; network errors
    become friendly messages. The API key appears only in headers; neither the
    URL nor error messages contain credentials.
    """
    url = config["api_base"] + path
    headers = {
        "Accept": "application/json",
        "X-Lang": config["lang"],
    }
    if config["api_key"]:
        headers["X-API-Key"] = config["api_key"]

    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with open_url(req, timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.getcode()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        payload = parse_json(raw)
        raise ApiError(exc.code, payload, error_message(payload, exc.code)) from exc
    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        if "timed out" in reason.lower() or "timeout" in reason.lower():
            msg = f"Network timeout ({timeout} seconds): {reason}"
        else:
            msg = f"Cannot reach service {config['api_base']}: {reason}"
        raise ApiError(0, None, msg) from exc
    except TimeoutError as exc:
        raise ApiError(0, None, f"Network timeout ({timeout} seconds)") from exc
    except OSError as exc:
        raise ApiError(0, None, f"Network error: {type(exc).__name__}") from exc

    payload = parse_json(raw)
    if status >= 400:
        raise ApiError(status, payload, error_message(payload, status))
    if payload is None:
        raise ApiError(-1, None, "Server returned empty or non-JSON content")
    return payload


def api_get(path, config, timeout):
    return request("GET", path, config, None, timeout)


def api_post(path, body, config, timeout):
    return request("POST", path, config, body, timeout)


def compact(value, limit=200):
    """Flatten a value into a short single-line string for summaries."""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + " ..."


def walk(value, prefix, depth, lines):
    """Recursively expand JSON into human-readable lines, capped by depth."""
    if depth > MAX_DEPTH:
        lines.append(f"{prefix}{compact(value)}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            label = f"{prefix}{key}"
            if isinstance(item, dict):
                lines.append(f"{label}:")
                walk(item, prefix + "  ", depth + 1, lines)
            elif isinstance(item, list):
                lines.append(f"{label} ({len(item)} items):")
                for idx, sub in enumerate(item, 1):
                    if isinstance(sub, (dict, list)):
                        lines.append(f"{prefix}  [{idx}]")
                        walk(sub, prefix + "    ", depth + 1, lines)
                    else:
                        lines.append(f"{prefix}  [{idx}] {compact(sub)}")
            else:
                lines.append(f"{label}: {compact(item)}")
    elif isinstance(value, list):
        for idx, sub in enumerate(value, 1):
            if isinstance(sub, (dict, list)):
                lines.append(f"{prefix}[{idx}]")
                walk(sub, prefix + "  ", depth + 1, lines)
            else:
                lines.append(f"{prefix}[{idx}] {compact(sub)}")
    else:
        lines.append(f"{prefix}{compact(value)}")


def human_lines(payload):
    lines = []
    walk(payload, "", 0, lines)
    return lines


def quota_lines(payload):
    data = payload if isinstance(payload, dict) else {}
    lines = [
        "== Daily free allowance ==",
        f"UTC date: {data.get('day_utc', '?')}    Plan: {data.get('plan', '?')}",
        f"Allowance: {data.get('free_limit', '?')}    Used: {data.get('free_used', '?')}    Remaining: {data.get('free_remaining', '?')}",
        f"Balance: {data.get('balance', '?')} {data.get('currency', '')}",
    ]
    buy = data.get("buy_url")
    if buy:
        lines.append(f"Buy credits: {buy}")
    lines.append("Rule: resets on a UTC day boundary; fixed daily amount, no accumulation or rollover.")
    return lines


def onboarding_lines(config):
    """Registration guidance for missing/failed auth: no credentials included."""
    base = config["api_base"]
    return [
        "------------------------------------------------------------",
        "First time here? Register to get an API key (free daily allowance):",
        f"  1) Open {SITE_URL} to register",
        f"     (service base URL: {base})",
        "  2) Confirm your email, then go to Account & Credits > Developer to generate an API key;",
        "  3) Set XRD_API_KEY, or write the key to ~/.config/xrd-cif/config.json;",
        "  4) Re-run doctor to self-check, then use search to retrieve.",
        "Daily free analyses are available; once used up, a 402 response includes the purchase link. No payment is handled here.",
        "------------------------------------------------------------",
    ]


def doctor_lines(payload, config):
    lines = [
        "== Self-check (doctor) ==",
        f"Service base URL: {config['api_base']}",
        "Connectivity: OK",
    ]
    if config["api_key"]:
        lines.append("API key: configured, X-API-Key header sent (value hidden)")
        lines.append("Auth result: server accepted the credential")
        lines.append("")
        lines.extend(quota_lines(payload))
    else:
        lines.append("API key: not configured (XRD_API_KEY and config file are both empty)")
        lines.append("Note: the server requires a valid API key; anonymous access is rejected.")
        lines.extend(onboarding_lines(config))
    return lines


def format_candidate(idx, item):
    if not isinstance(item, dict):
        return f"  {idx}. {compact(item)}"
    sid = item.get("structure_id") or item.get("id") or item.get("label") or "?"
    parts = [f"  {idx}. {sid}"]
    score = item.get("score", item.get("similarity"))
    if score is not None:
        parts.append(f"score={compact(score)}")
    verification = item.get("verification", item.get("decision"))
    if verification is not None:
        parts.append(f"verification={compact(verification)}")
    return "    ".join(parts)


def scalar(value):
    if isinstance(value, (dict, list)):
        return compact(value)
    return str(value)


def search_lines(payload):
    data = payload if isinstance(payload, dict) else {}
    lines = ["== Retrieval result =="]
    if data.get("history_id"):
        lines.append(f"history_id: {data['history_id']}")

    result = data.get("result")
    if isinstance(result, dict):
        if result.get("decision") is not None:
            lines.append(f"three-state decision: {scalar(result['decision'])}")
        candidates = result.get("candidates")
        if isinstance(candidates, list):
            lines.append(f"Top-{len(candidates)} candidates:")
            for idx, item in enumerate(candidates, 1):
                lines.append(format_candidate(idx, item))
        elif candidates is not None:
            lines.append(f"candidates: {compact(candidates)}")
        if result.get("meta"):
            lines.append(f"meta: {compact(result['meta'])}")
        if result.get("pattern"):
            lines.append(f"echoed pattern: {compact(result['pattern'])}")

    billing = data.get("billing")
    if isinstance(billing, dict):
        lines.append(
            f"billing: credits={billing.get('credits', '?')}"
            f" (0=daily free / 1=paid), balance after={billing.get('balance_after', '?')}"
        )
    quota = data.get("quota")
    if isinstance(quota, dict):
        lines.append(
            f"quota: free remaining {quota.get('free_remaining', '?')},"
            f" source {quota.get('source', '?')}"
        )
        buy = quota.get("buy_url") or data.get("buy_url")
        if buy:
            lines.append(f"Buy credits: {buy}")
    lines.append("Tip: use history --history-id to read per-candidate verification and render evidence.")
    return lines


def read_text_file(path, label):
    if not path:
        raise UsageError(f"This pattern-kind requires {label}")
    target = Path(path)
    if not target.is_file():
        raise UsageError(f"Cannot find {label}: {path}")
    try:
        return target.read_text(encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"Cannot read {label} {path}: {type(exc).__name__}") from exc


def build_pattern(args):
    kind = args.pattern_kind
    if kind == "simulate":
        return {
            "kind": "simulate",
            "structure_id": args.structure_id or "NaCl-rocksalt",
            "condition": args.condition or "clean",
        }
    if kind == "peaks":
        return {"kind": "peaks", "text": read_text_file(args.peaks_file, "peak-table file --peaks-file")}
    if kind == "xy":
        return {"kind": "xy", "text": read_text_file(args.xy_file, "pattern file --xy-file")}
    raise UsageError(f"Unsupported --pattern-kind: {kind}")


def emit(payload, as_json, lines):
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for line in lines:
            print(line)


def print_402(payload, stream):
    """Prominently print the purchase link and remaining quota; never fabricate results."""
    data = payload if isinstance(payload, dict) else {}
    quota = data.get("quota") if isinstance(data.get("quota"), dict) else {}
    buy = data.get("buy_url") or quota.get("buy_url") or "(no purchase link provided by server)"
    free = quota.get("free_remaining", data.get("free_remaining", "?"))
    day = quota.get("day_utc", "?")
    source = quota.get("source", "?")
    print("", file=stream)
    print("============================================================", file=stream)
    print("Out of credits: daily free allowance exhausted and balance is 0.", file=stream)
    print(f"  UTC date: {day}    Free remaining: {free}    Billing source: {source}", file=stream)
    print(f"  Buy analysis credits: {buy}", file=stream)
    print("Purchase credits at the link above, then retry.", file=stream)
    print("No result was produced. No results are fabricated or cached. / No results fabricated.", file=stream)
    print("============================================================", file=stream)


SPECIFIC = {
    403: (EXIT_403, "Forbidden: this credential cannot access the resource."),
    409: (EXIT_409, "request_id already used; change --request-id and retry."),
    429: (EXIT_429, "Rate limited; please retry later."),
}


def handle_error(exc, as_json, config=None):
    """Uniform error handling: non-zero exit codes, prominent 402, never fail silently."""
    if exc.status == 401:
        cfg = config or {"api_base": DEFAULT_BASE, "api_key": ""}
        print("[Error 401] API key missing, invalid, or revoked.", file=sys.stderr)
        stream = sys.stderr
        for line in onboarding_lines(cfg):
            print(line, file=stream)
        if as_json and exc.payload is not None:
            print(json.dumps(exc.payload, ensure_ascii=False, indent=2))
        return EXIT_401
    if exc.status == 402:
        stream = sys.stderr if as_json else sys.stdout
        print_402(exc.payload, stream)
        if as_json and exc.payload is not None:
            print(json.dumps(exc.payload, ensure_ascii=False, indent=2))
        return EXIT_402
    if exc.status == 403:
        code = exc.payload.get("code") if isinstance(exc.payload, dict) else None
        if code == "email_unverified":
            print("[Error 403] The account owning this token has not confirmed its email. "
                  "Click the confirmation link in your registration email, or resend it from "
                  "the account page on the website, then retry.", file=sys.stderr)
            return EXIT_403
    if exc.status in SPECIFIC:
        code, hint = SPECIFIC[exc.status]
        print(f"[Error {exc.status}] {hint} Details: {exc.message}", file=sys.stderr)
        return code
    if exc.status == 0:
        print(f"[Network error] {exc.message}", file=sys.stderr)
        return EXIT_NETWORK
    if exc.status == -1:
        print(f"[Response error] {exc.message}", file=sys.stderr)
        return EXIT_BAD_RESPONSE
    print(f"[Server error {exc.status}] {exc.message}", file=sys.stderr)
    return EXIT_HTTP


def dispatch(args, config):
    timeout = args.timeout
    if args.command == "quota":
        payload = api_get("/api/v1/quota", config, timeout)
        emit(payload, args.as_json, quota_lines(payload))
        return EXIT_OK
    if args.command == "account":
        payload = api_get("/api/v1/account", config, timeout)
        emit(payload, args.as_json, human_lines(payload))
        return EXIT_OK
    if args.command == "doctor":
        # With no key, the v1 quota endpoint only returns 401 and cannot check connectivity.
        # Probe the public health endpoint first, then branch on whether a key is configured.
        payload = api_get(HEALTH_PATH, config, timeout)
        if not config["api_key"]:
            lines = doctor_lines({"status": "ok"}, config)
            if args.as_json:
                emit({"status": "ok", "api_key": False,
                      "onboarding_url": SITE_URL, "service": config["api_base"]},
                     True, [])
            else:
                for line in lines:
                    print(line)
            return EXIT_OK
        quota = api_get("/api/v1/quota", config, timeout)
        emit(quota, args.as_json, doctor_lines(quota, config))
        return EXIT_OK
    if args.command == "search":
        pattern = build_pattern(args)
        body = {
            "pattern": pattern,
            "k": args.k,
            "request_id": args.request_id or str(uuid.uuid4()),
        }
        payload = api_post("/api/v1/search", body, config, timeout)
        emit(payload, args.as_json, search_lines(payload))
        return EXIT_OK
    if args.command == "reverse":
        body = {"structure_id": args.structure_id, "k": args.k}
        payload = api_post("/api/v1/reverse", body, config, timeout)
        emit(payload, args.as_json, human_lines(payload))
        return EXIT_OK
    if args.command == "history":
        hid = urllib.parse.quote(str(args.history_id), safe="")
        payload = api_get(f"/api/v1/history/{hid}", config, timeout)
        emit(payload, args.as_json, human_lines(payload))
        return EXIT_OK
    raise UsageError(f"Unknown command: {args.command}")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="xrd_client.py",
        description="CLI client for the XRD-CIF cross-modal crystal retrieval service (standard library only)",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Output raw JSON; default is a human-readable summary",
    )
    common.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default {DEFAULT_TIMEOUT})",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    sub.add_parser("quota", parents=[common], help="Show daily free allowance and balance")
    sub.add_parser("account", parents=[common], help="Show account and ledger summary")
    sub.add_parser("doctor", parents=[common], help="Check connectivity and API key")

    p_search = sub.add_parser("search", parents=[common], help="Pattern search for Top-K candidates")
    p_search.add_argument("--pattern-kind", choices=["simulate", "peaks", "xy"],
                          default="simulate", help="Pattern input type (default simulate)")
    p_search.add_argument("--structure-id", default="NaCl-rocksalt",
                          help="Structure ID used by simulate")
    p_search.add_argument("--condition", default="clean",
                          help="Condition used by simulate")
    p_search.add_argument("--peaks-file", help="Peak-table file (2θ and relative intensity) for peaks mode")
    p_search.add_argument("--xy-file", help="Continuous-pattern text file for xy mode")
    p_search.add_argument("--k", type=int, default=5, help="Number of candidates (default 5)")
    p_search.add_argument("--request-id", default=None,
                          help="Idempotency request ID; a UUID is generated if omitted")

    p_reverse = sub.add_parser("reverse", parents=[common], help="CIF structure → theoretical pattern")
    p_reverse.add_argument("--structure-id", default="NaCl-rocksalt", help="CIF structure ID")
    p_reverse.add_argument("--k", type=int, default=3, help="Number of matches (default 3)")

    p_history = sub.add_parser("history", parents=[common], help="Read full result and evidence")
    p_history.add_argument("--history-id", required=True, help="history_id returned by search")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config()
    try:
        return dispatch(args, config)
    except UsageError as exc:
        print(f"[Argument error] {exc}", file=sys.stderr)
        return EXIT_USAGE
    except ApiError as exc:
        return handle_error(exc, args.as_json, config)
    except Exception as exc:  # Catch-all: avoid a traceback that might leak credentials
        print(f"[Error] Unexpected exception: {type(exc).__name__}", file=sys.stderr)
        return EXIT_HTTP


if __name__ == "__main__":
    sys.exit(main())
