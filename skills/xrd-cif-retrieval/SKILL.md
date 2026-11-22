---
name: xrd-cif-retrieval
description: XRD 与 CIF 跨模态晶体检索 Skill，应在用户提出 XRD 物相鉴定、粉末衍射谱 pXRD 峰位解释、衍射谱匹配候选晶体结构、由 CIF 结构反查理论衍射谱、要求核对 SUPPORT/CONTRADICT/INSUFFICIENT 三态物理规则复核证据，或查询每日免费额度与账户余额及购买额度时触发；借助 scripts/xrd_client.py 调用远程检索服务，返回 Top-K 候选结构与可追溯证据，并在免费额度用尽时清晰输出购买链接与剩余额度。
agent_created: true
---

# XRD-CIF 跨模态晶体检索

## 概述

封装远程 XRD-CIF 跨模态检索服务：输入 X 射线衍射谱，返回 Top-K 候选晶体结构，并经教材抽取的物理规则做独立三态复核（SUPPORT / CONTRADICT / INSUFFICIENT），输出可追溯证据。全部能力通过 `scripts/xrd_client.py` 以命令行方式调用。服务按解析次数（credits）计费，每账户每日有免费额度，用尽后须到网站购买。

## 触发时机

在下列请求出现时启用本 Skill：

- 依据 XRD / pXRD 衍射谱做物相鉴定或峰位解释；
- 将衍射谱匹配到候选晶体结构、索取 Top-K 候选清单；
- 由 CIF 结构反查理论衍射谱并核对命中；
- 查看三态复核结论与每个候选的 verification / render 证据；
- 查询每日免费额度、账户余额、账本流水或购买额度入口。

## 配置

按以下优先级读取服务地址与凭据；勿将 API Key 写入日志、命令回显或输出：

- 基址：环境变量 `XRD_API_BASE`，默认 `https://xrdcif.com`（公开服务，本地开发可用环境变量覆盖）；
- API Key：环境变量 `XRD_API_KEY`，或 `~/.config/xrd-cif/config.json` 中的 `api_key` / `api_base`；
- 语言：环境变量 `XRD_LANG`，默认 `en`，随每次请求写入 `X-Lang` 头。

获取 API Key：打开 `https://xrdcif.com` 注册 → 确认邮箱 → 进入「账户与额度 / 开发者」栏目生成 API Key → 写入环境变量 `XRD_API_KEY` 或配置文件。无 Key 时先执行 `doctor`，客户端会自检连通性并打印注册引导；401 响应同样附带引导。购买链接由服务端 `quota` 与 402 响应返回，勿在客户端写死。

## 工作流

1. 执行 `python scripts/xrd_client.py doctor` 自检连通性与 Key 有效性。若未配置 Key，客户端会打印注册引导（含网站地址与生成 Key 步骤）——此时应把引导如实呈现给用户，不得代替用户注册、不得伪造 Key。
2. 有 Key 后执行 `python scripts/xrd_client.py quota` 读取当日免费剩余额度、余额与购买链接。
3. 构造衍射谱并执行 `search`：`simulate` 使用内置演示结构，`peaks` 读取 2θ 与相对强度峰表，`xy` 读取连续谱；用 `--k` 指定候选数，`--request-id` 传入 UUID 以保证幂等。
4. 需要逐候选证据时执行 `history` 读取 verification 与 render 文本；需要结构反查时执行 `reverse`。
5. 检查账户明细时执行 `account`。
6. 遇到 HTTP 402（免费额度与余额均耗尽）时，须原样打印响应中的购买链接与剩余额度，停止本次检索；绝不静默失败，绝不伪造或缓存结果。Never fabricate results.

## 命令速查

| 子命令 | 用途 | 主要参数 |
| --- | --- | --- |
| `doctor` | 自检连通性与 Key | `--json` `--timeout` |
| `quota` | 当日免费额度与余额 | `--json` `--timeout` |
| `search` | 衍射谱检索 Top-K | `--pattern-kind` `--structure-id` `--condition` `--peaks-file` `--xy-file` `--k` `--request-id` `--json` |
| `reverse` | CIF 反查理论谱 | `--structure-id` `--k` `--json` |
| `history` | 完整结果与证据 | `--history-id` `--json` |
| `account` | 账户与账本流水 | `--json` |

所有子命令支持 `--json` 输出原始 JSON，默认输出人类可读摘要；`--timeout` 设置显式超时秒数。完整端点、字段、错误码与计费口径见 `references/api.md`；安装、发布与购买流程见 `README.md`。

## 计费与合规边界

- 免费额度按 UTC 日切重置，每日固定、不累积、不跨日结转；`billing.credits` 标记本次是否消耗付费额度，`quota.source` 标记来源为 `daily_free` 或 `credits`。
- 结果内含同源自评指标，仅作检索参考与证据追溯，不得用于营销宣称准确率。Self-evaluation metrics are not accuracy claims.
- 支付由网站侧完成（Paddle 商户密钥在服务端），本 Skill 与客户端不接触支付凭据、不写死购买链接。Payment is handled server-side; this Skill never touches payment credentials.

## 资源

- `scripts/xrd_client.py`：纯标准库命令行客户端，直接运行，零第三方依赖。
- `references/api.md`：完整 API 契约、字段、错误码与合规声明。
- `README.md`：安装、获取 Key、额度购买、各市场发布说明与诚实边界。
