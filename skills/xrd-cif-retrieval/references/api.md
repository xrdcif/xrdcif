# XRD-CIF 检索服务 API 契约（客户端参考）

本文件是 `scripts/xrd_client.py` 所依赖的完整服务端契约，供开发与排障时查阅。服务端按此契约实现，客户端只消费、不修改。所有响应均为 JSON；POST 请求体为 JSON，GET 无请求体。

## 1. 基址与配置

- 基址：环境变量 `XRD_API_BASE`，默认 `https://xrdcif.com`（本地开发可用环境变量覆盖）。
- 备选配置文件：`~/.config/xrd-cif/config.json`，格式 `{"api_key": "...", "api_base": "..."}`。
- 优先级：环境变量 > 配置文件 > 默认值。
- API Key：环境变量 `XRD_API_KEY`，或配置文件的 `api_key`。
- 语言：环境变量 `XRD_LANG`，默认 `en`。

## 2. 认证与通用请求头

| 请求头 | 取值 | 说明 |
| --- | --- | --- |
| `X-API-Key` | API Key | 主认证方式，客户端使用该头 |
| `Authorization` | `Bearer <key>` | 服务端同时支持的等价方式 |
| `X-Lang` | `XRD_LANG` 或默认 `en` | 每次请求均须携带 |
| `Content-Type` | `application/json` | POST 请求 |
| `Accept` | `application/json` | 所有请求 |

安全约定：API Key 仅出现在请求头，绝不写入 URL、标准输出、标准错误或日志。Never log the API key.

## 3. 端点

### 3.1 GET /api/v1/quota

查询当日免费额度、账户余额与购买链接。无请求体。

响应示例：

```json
{
  "free_limit": 5,
  "free_used": 2,
  "free_remaining": 3,
  "day_utc": "2026-11-13",
  "balance": 20,
  "currency": "USD",
  "buy_url": "https://xrdcif.com/pricing",
  "plan": "free"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `free_limit` | 当日免费额度上限 |
| `free_used` | 当日已用免费次数 |
| `free_remaining` | 当日剩余免费次数 |
| `day_utc` | 额度所属的 UTC 日期 |
| `balance` | 付费解析次数余额（credits） |
| `currency` | 余额计价币种 |
| `buy_url` | 购买额度的网站链接，由服务端返回，客户端不得写死 |
| `plan` | 当前套餐标识 |

上例 `buy_url` 中的 `<host>` 为占位符，实际值由服务端返回，指向网站定价区。

### 3.2 POST /api/v1/search

衍射谱检索，返回 Top-K 候选结构、三态复核结论与计费信息。

请求体：

```json
{
  "pattern": {"kind": "simulate", "structure_id": "NaCl-rocksalt", "condition": "clean"},
  "k": 5,
  "request_id": "<uuid>"
}
```

`pattern` 支持三种 `kind`：

| kind | 结构 | 用途 |
| --- | --- | --- |
| `simulate` | `{"kind":"simulate","structure_id":"NaCl-rocksalt","condition":"clean"}` | 使用内置演示结构生成衍射谱 |
| `peaks` | `{"kind":"peaks","text":"31.70 1.000\n45.45 0.55\n..."}` | 2θ 与相对强度峰表文本 |
| `xy` | `{"kind":"xy","text":"10.00 0.001\n..."}` | 连续谱文本 |

`k` 为返回候选数量；`request_id` 为幂等键，重复提交相同值返回 409。

成功响应：

```json
{
  "history_id": "...",
  "result": {"decision": "...", "candidates": [], "pattern": {}, "meta": {}},
  "billing": {"credits": 0, "balance_after": 20},
  "quota": {"free_remaining": 3, "source": "daily_free"}
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `history_id` | 本次结果 ID，供 `history` 端点取回完整结果 |
| `result.decision` | 三态复核结论（SUPPORT / CONTRADICT / INSUFFICIENT） |
| `result.candidates` | Top-K 候选结构列表，含结构标识、得分与复核信息 |
| `result.pattern` | 服务端回显的衍射谱输入 |
| `result.meta` | 检索元信息 |
| `billing.credits` | 本次消耗的付费额度；0 表示使用每日免费额度，1 表示消耗付费余额 |
| `billing.balance_after` | 计费后的余额 |
| `quota.free_remaining` | 计费后剩余免费次数 |
| `quota.source` | 本次计费来源：`daily_free` 或 `credits` |

### 3.3 POST /api/v1/reverse

由 CIF 结构反查理论衍射谱并返回命中结果。

请求体：

```json
{"structure_id": "NaCl-rocksalt", "k": 3}
```

响应为理论谱反查命中结果（JSON），具体命中字段由服务端定义，客户端以通用结构化摘要或 `--json` 原始 JSON 呈现。

### 3.4 GET /api/v1/history/<history_id>

取回完整检索结果，含每个候选的 `verification` 证据与 `render` 文本。`history_id` 来自 `search` 响应；客户端对该路径段做 URL 转义。

### 3.5 GET /api/v1/account

返回账户信息、余额与账本流水摘要（JSON）。

## 4. 错误码

| 状态 | 类型 | 含义 | 客户端处理 |
| --- | --- | --- | --- |
| 200 | - | 成功 | 输出摘要或原始 JSON |
| 401 | `AuthError` | API Key 缺失、无效或已撤销 | 打印注册引导（网站地址 + 生成 Key 步骤），退出码非零 |
| 402 | `InsufficientCredits` | 免费额度用尽且余额为 0 | 醒目打印购买链接与剩余额度，停止检索，退出码非零 |
| 403 | 越权 / 邮箱未确认 | 当前凭据无权访问；或该 Token 所属账户未完成邮箱确认（`code=email_unverified`） | 提示越权；未确认时引导用户查收确认邮件或在网站账户页重发 |
| 409 | 冲突 | `request_id` 重复 | 提示更换 `request_id` 后重试 |
| 429 | 限流 | 请求过于频繁 | 提示稍后重试 |
| 5xx | 服务端错误 | 服务异常 | 输出错误详情，退出码非零 |
| 本地 | 网络/超时 | 连接失败、超时、非 JSON 响应 | 友好提示，退出码非零 |

402 响应体示例：

```json
{
  "error": "...",
  "type": "InsufficientCredits",
  "quota": {"free_remaining": 0, "day_utc": "2026-11-13", "source": "credits"},
  "buy_url": "https://xrdcif.com/pricing"
}
```

客户端约定：必须识别 402，清晰打印 `buy_url` 与 `quota` 中的剩余额度，返回非零退出码；绝不静默失败，绝不伪造或缓存结果。Never fabricate results on 402.

## 5. 免费额度与计费规则

- 免费额度按 UTC 日切（字段 `day_utc`），每日重置。
- 每日额度固定为 `free_limit`，不累积、不跨日结转。
- 计费顺序：先消耗当日免费额度，再消耗付费余额 `balance`。
- `quota.source` 标记本次来源为 `daily_free`（免费）或 `credits`（付费）。
- `billing.credits` 标记本次是否消耗付费额度：0 免费，1 付费。
- 当免费额度与付费余额均为 0 时，返回 402，须到 `buy_url` 指向的网站定价区购买解析次数（credits）后方可继续。
- 购买与支付在网站侧完成，Skill 与客户端不处理支付凭据。

## 6. 合规声明

- 结果内含同源自评指标（same-source self-evaluation metrics），仅用于检索参考与证据追溯，不可用于营销宣称准确率。Self-evaluation metrics are not accuracy claims.
- 三态复核 SUPPORT / CONTRADICT / INSUFFICIENT 是基于教材抽取物理规则的独立复核结论，不构成对鉴定准确率的保证。
- 支付由网站侧 Paddle 商户账号完成，本契约与客户端不涉及支付凭据。Payments are handled server-side via Paddle; this contract never covers payment credentials.
- 客户端不得回显 API Key，不得把 Key 写入日志或错误信息。

## 7. 客户端行为约定

- 纯 Python 标准库 `urllib`，零第三方依赖，可直接 `python xrd_client.py <子命令>`。
- 显式超时；网络错误给出友好提示；所有失败路径返回非零退出码。
- `--json` 输出原始 JSON，默认输出人类可读摘要。
- 每次请求携带 `X-Lang`；GET / POST 均携带 `Accept: application/json`。
