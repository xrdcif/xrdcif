#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""XRD-CIF 跨模态晶体检索服务命令行客户端。

仅使用 Python 标准库（urllib），无第三方依赖，可直接运行：
    python xrd_client.py <子命令> [选项]

子命令：
    quota    查询当日免费额度与账户余额
    search   衍射谱检索 Top-K 候选结构
    reverse  由 CIF 结构反查理论衍射谱
    history  读取完整结果与逐候选证据
    account  查询账户与账本流水
    doctor   自检连通性与 API Key 是否有效

安全约定：API Key 只放入请求头，绝不写入标准输出、标准错误或日志。
Never print or log the API key.
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

# Windows 控制台默认编码可能无法输出中文，统一切换为 UTF-8。
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 默认指向公开服务（引流落点）；本地开发可用 XRD_API_BASE 或配置文件覆盖。
DEFAULT_BASE = "https://xrdcif.com"
# 注册引导页：无 Key 的陌生用户从这里获取 Key，这是引流的起点。
SITE_URL = (os.environ.get("XRD_SITE_URL") or "https://xrdcif.com").rstrip("/")
# 公开连通性探测端点（无需 Key），供 doctor 在尚无 Key 时自检使用。
HEALTH_PATH = "/api/health"
CONFIG_PATH = Path.home() / ".config" / "xrd-cif" / "config.json"
DEFAULT_TIMEOUT = 15.0
MAX_DEPTH = 4

# 退出码：便于外部脚本按结果分支处理。
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
    """参数或输入文件不合法。"""


class ApiError(Exception):
    """服务端或网络错误。

    status: HTTP 状态码；0 表示网络或超时；-1 表示响应不是合法 JSON。
    payload: 解析后的 JSON（可能为 None）。
    message: 面向用户的简短说明，不含任何凭据。
    """

    def __init__(self, status, payload, message):
        super().__init__(message)
        self.status = status
        self.payload = payload
        self.message = message


def load_config():
    """读取基址、API Key 与语言。

    优先级：环境变量 XRD_API_BASE / XRD_API_KEY / XRD_LANG，
    其次为 ~/.config/xrd-cif/config.json 的 api_base / api_key，
    最后回退到默认值。返回值含 Key，但任何调用方都不得打印该值。
    """
    api_base = os.environ.get("XRD_API_BASE")
    api_key = os.environ.get("XRD_API_KEY")
    lang = os.environ.get("XRD_LANG") or "en"

    cfg = {}
    if CONFIG_PATH.is_file():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[警告] 配置文件不可读，已忽略：{type(exc).__name__}", file=sys.stderr)

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
    """把响应文本解析为 JSON，失败返回 None。"""
    if not raw or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def error_message(payload, status):
    """从错误响应提取 error / type 字段，构造不含凭据的说明。"""
    if isinstance(payload, dict):
        err = payload.get("error") or payload.get("message")
        if err:
            typ = payload.get("type")
            return f"{err}" + (f" [type={typ}]" if typ else "")
    return f"HTTP {status}"


def open_url(req, timeout):
    """打开请求；本地回环地址绕过 HTTP 代理。

    默认基址为 127.0.0.1，若环境设置了 HTTP_PROXY，代理会把本地
    请求拦成 5xx；此处对 localhost / 127.0.0.1 / ::1 强制直连。
    Bypass proxies for loopback hosts.
    """
    host = (urllib.parse.urlsplit(req.full_url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)


def request(method, path, config, body, timeout):
    """发起一次 HTTP 请求，返回解析后的 JSON。

    统一携带 X-API-Key 与 X-Lang 头；显式超时；网络错误转为友好提示。
    API Key 只在请求头中出现，URL 与错误信息均不含凭据。
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
            msg = f"网络超时（{timeout} 秒）：{reason}"
        else:
            msg = f"无法连接服务 {config['api_base']}：{reason}"
        raise ApiError(0, None, msg) from exc
    except TimeoutError as exc:
        raise ApiError(0, None, f"网络超时（{timeout} 秒）") from exc
    except OSError as exc:
        raise ApiError(0, None, f"网络错误：{type(exc).__name__}") from exc

    payload = parse_json(raw)
    if status >= 400:
        raise ApiError(status, payload, error_message(payload, status))
    if payload is None:
        raise ApiError(-1, None, "服务端返回空内容或非 JSON 响应")
    return payload


def api_get(path, config, timeout):
    return request("GET", path, config, None, timeout)


def api_post(path, body, config, timeout):
    return request("POST", path, config, body, timeout)


def compact(value, limit=200):
    """把值压成单行短文本，便于摘要展示。"""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + " ..."


def walk(value, prefix, depth, lines):
    """递归展开 JSON 为人类可读行，限制深度避免输出过长。"""
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
                lines.append(f"{label} ({len(item)} 项):")
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
        "== 每日免费额度 ==",
        f"UTC 日期：{data.get('day_utc', '?')}    套餐：{data.get('plan', '?')}",
        f"免费额度：{data.get('free_limit', '?')}    已用：{data.get('free_used', '?')}    剩余：{data.get('free_remaining', '?')}",
        f"账户余额：{data.get('balance', '?')} {data.get('currency', '')}",
    ]
    buy = data.get("buy_url")
    if buy:
        lines.append(f"购买额度：{buy}")
    lines.append("规则：按 UTC 日切重置，每日固定额度，不累积、不跨日结转。")
    return lines


def onboarding_lines(config):
    """无 Key / 鉴权失败时的注册引导：引流的落地话术，不含任何凭据。"""
    base = config["api_base"]
    return [
        "------------------------------------------------------------",
        "首次使用请先注册并获取 API Key（免费额度当日可领）：",
        f"  1) 打开网站注册：{SITE_URL}",
        f"     （服务基址：{base}）",
        "  2) 注册后确认邮箱 → 进入「账户与额度 / 开发者」栏目 → 生成 API Key；",
        "  3) 把 Key 写入环境变量 XRD_API_KEY，或配置文件 ~/.config/xrd-cif/config.json；",
        "  4) 重新运行 doctor 自检，然后即可用 search 检索。",
        "每日有免费解析额度，用尽后 402 响应会给出购买链接；本客户端不处理支付。",
        "------------------------------------------------------------",
    ]


def doctor_lines(payload, config):
    lines = [
        "== 自检 doctor ==",
        f"服务基址：{config['api_base']}",
        "连通性：正常",
    ]
    if config["api_key"]:
        lines.append("API Key：已配置，请求已携带 X-API-Key 头（值不显示 / value hidden）")
        lines.append("鉴权结果：服务端接受该凭据")
        lines.append("")
        lines.extend(quota_lines(payload))
    else:
        lines.append("API Key：未配置（XRD_API_KEY 与配置文件均为空）")
        lines.append("提示：服务端要求有效 API Key，匿名访问会被拒绝。")
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
    lines = ["== 检索结果 =="]
    if data.get("history_id"):
        lines.append(f"history_id：{data['history_id']}")

    result = data.get("result")
    if isinstance(result, dict):
        if result.get("decision") is not None:
            lines.append(f"三态结论 decision：{scalar(result['decision'])}")
        candidates = result.get("candidates")
        if isinstance(candidates, list):
            lines.append(f"候选结构 Top-{len(candidates)}：")
            for idx, item in enumerate(candidates, 1):
                lines.append(format_candidate(idx, item))
        elif candidates is not None:
            lines.append(f"candidates：{compact(candidates)}")
        if result.get("meta"):
            lines.append(f"meta：{compact(result['meta'])}")
        if result.get("pattern"):
            lines.append(f"回显 pattern：{compact(result['pattern'])}")

    billing = data.get("billing")
    if isinstance(billing, dict):
        lines.append(
            f"本次计费：credits={billing.get('credits', '?')}"
            f"（0=免费额度 / 1=付费额度），计费后余额={billing.get('balance_after', '?')}"
        )
    quota = data.get("quota")
    if isinstance(quota, dict):
        lines.append(
            f"额度：免费剩余 {quota.get('free_remaining', '?')}，"
            f"来源 {quota.get('source', '?')}"
        )
        buy = quota.get("buy_url") or data.get("buy_url")
        if buy:
            lines.append(f"购买额度：{buy}")
    lines.append("提示：用 history --history-id 读取逐候选 verification 与 render 证据。")
    return lines


def read_text_file(path, label):
    if not path:
        raise UsageError(f"该 pattern-kind 必须提供 {label}")
    target = Path(path)
    if not target.is_file():
        raise UsageError(f"找不到{label}：{path}")
    try:
        return target.read_text(encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"无法读取{label} {path}：{type(exc).__name__}") from exc


def build_pattern(args):
    kind = args.pattern_kind
    if kind == "simulate":
        return {
            "kind": "simulate",
            "structure_id": args.structure_id or "NaCl-rocksalt",
            "condition": args.condition or "clean",
        }
    if kind == "peaks":
        return {"kind": "peaks", "text": read_text_file(args.peaks_file, "峰表文件 --peaks-file")}
    if kind == "xy":
        return {"kind": "xy", "text": read_text_file(args.xy_file, "连续谱文件 --xy-file")}
    raise UsageError(f"不支持的 --pattern-kind：{kind}")


def emit(payload, as_json, lines):
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for line in lines:
            print(line)


def print_402(payload, stream):
    """醒目打印购买链接与剩余额度，明确绝不伪造结果。"""
    data = payload if isinstance(payload, dict) else {}
    quota = data.get("quota") if isinstance(data.get("quota"), dict) else {}
    buy = data.get("buy_url") or quota.get("buy_url") or "（服务端未提供购买链接）"
    free = quota.get("free_remaining", data.get("free_remaining", "?"))
    day = quota.get("day_utc", "?")
    source = quota.get("source", "?")
    print("", file=stream)
    print("============================================================", file=stream)
    print("额度不足：每日免费额度已用尽，且账户余额为 0。", file=stream)
    print(f"  当日 UTC：{day}    免费剩余：{free}    计费来源：{source}", file=stream)
    print(f"  购买解析额度：{buy}", file=stream)
    print("请到上述链接购买额度后重试。", file=stream)
    print("本次未产生检索结果，客户端不会伪造或缓存任何结果。/ No results fabricated.", file=stream)
    print("============================================================", file=stream)


SPECIFIC = {
    403: (EXIT_403, "越权访问，当前凭据无权调用该资源。"),
    409: (EXIT_409, "request_id 重复，请更换 --request-id 后重试。"),
    429: (EXIT_429, "请求被限流，请稍后重试。"),
}


def handle_error(exc, as_json, config=None):
    """统一处理错误：非零退出码、402 醒目提示、绝不静默失败。"""
    if exc.status == 401:
        cfg = config or {"api_base": DEFAULT_BASE, "api_key": ""}
        print("[错误 401] API Key 缺失、无效或已撤销。", file=sys.stderr)
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
            print("[错误 403] 该 Token 所属账户尚未完成邮箱确认：请到注册邮箱点击确认链接，"
                  "或登录网站账户页重新发送确认邮件后再试。", file=sys.stderr)
            return EXIT_403
    if exc.status in SPECIFIC:
        code, hint = SPECIFIC[exc.status]
        print(f"[错误 {exc.status}] {hint} 详情：{exc.message}", file=sys.stderr)
        return code
    if exc.status == 0:
        print(f"[网络错误] {exc.message}", file=sys.stderr)
        return EXIT_NETWORK
    if exc.status == -1:
        print(f"[响应错误] {exc.message}", file=sys.stderr)
        return EXIT_BAD_RESPONSE
    print(f"[服务错误 {exc.status}] {exc.message}", file=sys.stderr)
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
        # 无 Key 时打 v1 配额接口只会拿到 401，无法自检连通性。
        # 先探测公开的 health 端点确认服务可达，再按是否配置 Key 分支输出。
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
    raise UsageError(f"未知子命令：{args.command}")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="xrd_client.py",
        description="XRD-CIF 跨模态晶体检索服务命令行客户端（纯标准库）",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--json", action="store_true", dest="as_json",
        help="输出原始 JSON；默认输出人类可读摘要",
    )
    common.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT,
        help=f"请求超时秒数（默认 {DEFAULT_TIMEOUT}）",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="子命令")

    sub.add_parser("quota", parents=[common], help="查询当日免费额度与账户余额")
    sub.add_parser("account", parents=[common], help="查询账户与账本流水摘要")
    sub.add_parser("doctor", parents=[common], help="自检连通性与 API Key")

    p_search = sub.add_parser("search", parents=[common], help="衍射谱检索 Top-K 候选结构")
    p_search.add_argument("--pattern-kind", choices=["simulate", "peaks", "xy"],
                          default="simulate", help="衍射谱输入类型（默认 simulate）")
    p_search.add_argument("--structure-id", default="NaCl-rocksalt",
                          help="simulate 使用的结构 ID")
    p_search.add_argument("--condition", default="clean",
                          help="simulate 使用的条件")
    p_search.add_argument("--peaks-file", help="peaks 模式的 2θ 与相对强度峰表文件")
    p_search.add_argument("--xy-file", help="xy 模式的连续谱文本文件")
    p_search.add_argument("--k", type=int, default=5, help="返回候选数量（默认 5）")
    p_search.add_argument("--request-id", default=None,
                          help="幂等请求 ID；缺省自动生成 UUID")

    p_reverse = sub.add_parser("reverse", parents=[common], help="由 CIF 结构反查理论衍射谱")
    p_reverse.add_argument("--structure-id", default="NaCl-rocksalt", help="CIF 结构 ID")
    p_reverse.add_argument("--k", type=int, default=3, help="返回命中数量（默认 3）")

    p_history = sub.add_parser("history", parents=[common], help="读取完整结果与证据")
    p_history.add_argument("--history-id", required=True, help="search 返回的 history_id")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config()
    try:
        return dispatch(args, config)
    except UsageError as exc:
        print(f"[参数错误] {exc}", file=sys.stderr)
        return EXIT_USAGE
    except ApiError as exc:
        return handle_error(exc, args.as_json, config)
    except Exception as exc:  # 兜底：避免堆栈回显可能携带的凭据
        print(f"[错误] 未预期异常：{type(exc).__name__}", file=sys.stderr)
        return EXIT_HTTP


if __name__ == "__main__":
    sys.exit(main())
