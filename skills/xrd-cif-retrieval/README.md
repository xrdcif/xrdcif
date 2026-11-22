# xrd-cif-retrieval 引流 Skill 包

把一个 XRD（X 射线衍射谱）↔ CIF（晶体结构）跨模态检索网站的能力封装为可发布到各 Skill 市场的 Skill：输入衍射谱，返回 Top-K 候选结构，经物理规则做独立三态复核（SUPPORT / CONTRADICT / INSUFFICIENT），输出可追溯证据。Skill 本身只作为引流与调用入口，真正的检索、计费与购买发生在网站侧。

每个用户每天有一定免费解析额度，用完必须到网站购买额度（credits）。客户端在额度耗尽时会清晰打印购买链接与剩余额度，绝不静默失败、绝不伪造结果。

## 目录结构

```
xrd-cif-retrieval/
├── SKILL.md                 # Skill 入口，含 frontmatter 与工作流指令
├── README.md                # 本文件：安装、配置、购买、发布说明
├── scripts/
│   └── xrd_client.py        # 纯标准库命令行客户端（urllib，零第三方依赖）
└── references/
    └── api.md               # 完整 API 契约、字段、错误码与合规声明
```

目录名与文件名均为 ASCII 小写连字符风格（固定名 `SKILL.md`、`README.md` 及任务指定的 `scripts/xrd_client.py` 除外）。无 assets 目录，本 Skill 不需要模板、图片或字体等资源。

## 安装

以 WorkBuddy 用户级安装为例：把本目录（或解压后的目录）放到用户级 skills 目录 `~/.workbuddy/skills/` 下，保持目录名为 `xrd-cif-retrieval`。

```
~/.workbuddy/skills/xrd-cif-retrieval/SKILL.md
~/.workbuddy/skills/xrd-cif-retrieval/scripts/xrd_client.py
~/.workbuddy/skills/xrd-cif-retrieval/references/api.md
```

发布包通常是 zip：解压后得到 `xrd-cif-retrieval/` 目录，将其整体放入对应平台的用户级 skills 目录即可。不同平台的用户级目录名以该平台官方文档为准，本文件不假定具体路径。安装后无需构建，客户端用系统 Python 直接运行。

## 配置与获取 API Key

客户端按以下优先级读取配置：环境变量 > 配置文件 > 默认值。

- `XRD_API_BASE`：服务基址，默认 `https://xrdcif.com`（本地开发可用环境变量覆盖）。
- `XRD_API_KEY`：API Key。
- `XRD_LANG`：请求语言，默认 `en`，随请求写入 `X-Lang` 头。
- 配置文件 `~/.config/xrd-cif/config.json`：`{"api_key": "...", "api_base": "..."}`。

获取 API Key 的路径（在网站内操作，不通过客户端）：打开 `https://xrdcif.com` 注册 → 确认邮箱 → 账户与额度 / 开发者 → 生成 API Key，然后把 Key 写入环境变量 `XRD_API_KEY` 或上述配置文件。尚未配置 Key 时先跑 `python scripts/xrd_client.py doctor`：客户端会自检服务连通性并打印上述注册引导；任何需要鉴权的端点返回 401 时也会附带同样的引导，不会只丢一句"Key 无效"。

API Key 只会被放入请求头 `X-API-Key`（服务端同时支持 `Authorization: Bearer`），不会出现在 URL、日志或任何输出中。购买链接 `buy_url` 由服务端 `quota` 与 402 响应返回，客户端不写死任何购买地址。

## 每日免费额度与购买路径

- 免费额度按 UTC 日切重置，每日固定次数，不累积、不跨日结转。
- 调用顺序：先扣当日免费额度，再扣付费余额（credits）。
- `quota` 子命令可随时查看 `free_remaining`、`balance` 与 `buy_url`。
- 当免费额度与余额都为 0 时，`search` 返回 HTTP 402（类型 `InsufficientCredits`）；客户端会醒目打印购买链接与剩余额度，返回非零退出码，且明确声明未伪造结果。
- 购买路径：到网站账户页或定价页（即 `buy_url` 指向的页面）购买解析额度，完成后即可继续检索。支付由网站侧通过 Paddle 商户账号完成，本 Skill 与客户端不接触支付凭据。

## 快速开始

以下命令在 Skill 根目录执行，或直接指向 `scripts/xrd_client.py`。

```bash
# 自检连通性与 Key 是否有效
python scripts/xrd_client.py doctor

# 查看当日免费额度、余额与购买链接
python scripts/xrd_client.py quota

# 内置演示结构检索（默认 simulate / NaCl-rocksalt / clean）
python scripts/xrd_client.py search

# 峰表模式（2θ 与相对强度）
python scripts/xrd_client.py search --pattern-kind peaks --peaks-file peaks.txt --k 5

# 连续谱模式
python scripts/xrd_client.py search --pattern-kind xy --xy-file pattern.xy --k 5 --json

# 由 CIF 结构反查理论衍射谱
python scripts/xrd_client.py reverse --structure-id NaCl-rocksalt --k 3

# 读取完整结果与逐候选 verification / render 证据（HISTORY_ID 替换为实际值）
python scripts/xrd_client.py history --history-id HISTORY_ID

# 账户与账本流水
python scripts/xrd_client.py account
```

所有子命令支持 `--json`（输出原始 JSON）与 `--timeout`（显式超时秒数）。完整端点、字段与错误码见 `references/api.md`。

## 校验与打包

本包使用 skill-creator 的初始化与打包脚本生成并校验：

```bash
# SKILL_CREATOR 指向 skill-creator 目录，OUT 为 skills 目录，DIST 为输出目录
python "$SKILL_CREATOR/scripts/init_skill.py" xrd-cif-retrieval --path "$OUT"
python "$SKILL_CREATOR/scripts/package_skill.py" "$OUT/xrd-cif-retrieval" "$DIST"
```

`package_skill.py` 会先校验 `SKILL.md` 的 frontmatter，再打包为 `xrd-cif-retrieval.zip`。校验失败时须修复后重跑，直到成功。

## 发布到各 Skill 市场

各市场通常要求：一个含 YAML frontmatter 的 `SKILL.md`、`scripts/` 与 `references/` 等资源目录、规范的目录结构，以及可分发的 zip 包。本包已按此结构组织。

现实可落地的发布渠道（按推荐顺序）：

- **GitHub（立即可做，首选）**：建公开仓库放源码，Release 中附带 `xrd-cif-retrieval.zip`；仓库 README 说明安装、API Key 获取与额度购买路径。这是唯一完全不受平台审核约束、随时可发且可长期沉淀搜索流量的渠道。
- **Claude Skills / 其他支持 SKILL.md 规范的平台**：按其用户级 skills 目录约定放置本目录（以各平台官方文档为准）；frontmatter 与指令式写法已符合常见 Skills 规范。注意这些平台多为"用户自行安装本地 skill"，而非中心化上架商店。
- **WorkBuddy**：截止本文件编写时，WorkBuddy 提供的是「打包 zip 分享 / 用户自行安装」机制，**没有面向个人开发者的公开投稿上架入口**。不要假设存在一个可以提交审核的"技能市场投稿框"；如平台后续开放投稿，再按其官方最新说明提交。

各平台规则会随时间变化，本文件不编造任何具体提交地址；发布前以官方最新文档为准。zip 内顶层目录为 `xrd-cif-retrieval/`，解压即用。

**引流闭环提醒**：本 Skill 的价值不在 Skill 本身，而在把用户带到网站注册。发布页/README 的第一屏必须突出"免费注册领每日额度"，且 `doctor` 与 401 引导会打印 `https://xrdcif.com`——这个地址就是引流落点，不要改写成别处。

## 诚实边界与合规

- 支付经网站侧 Paddle 商户账号完成，本 Skill 与客户端不接触支付凭据。Payments are handled server-side via Paddle; this Skill never touches payment credentials.
- 结果含同源自评指标，仅用于检索参考与证据追溯，不可用于营销宣称准确率。Self-evaluation metrics are not accuracy claims.
- 三态复核结论不构成对鉴定准确率的保证。
- 免费额度用尽时不伪造、不缓存结果；402 时清晰给出购买链接与剩余额度。No fabricated results on 402.
- API Key 不回显、不写日志。Never log the API key.

## 许可与维护

本 Skill 包为引流用途，随主站 API 契约演进同步更新 `references/api.md`。服务端契约变更时，客户端仅按契约消费，不自行改写接口。

---

## EN Summary

This Skill package wraps a commercial XRD-to-CIF cross-modal crystal retrieval service for distribution on Skill marketplaces (WorkBuddy Skill Market, Claude Skills, GitHub). It ships `SKILL.md`, a dependency-free standard-library CLI client `scripts/xrd_client.py` (urllib only), and the full API contract in `references/api.md`.

Install by placing the `xrd-cif-retrieval/` folder (or unzipping the release zip) into the platform's user-level skills directory. Register at `https://xrdcif.com`, confirm email, then generate an API Key under Account / Developer and set `XRD_API_KEY` (or `~/.config/xrd-cif/config.json`); the base URL defaults to `XRD_API_BASE` or `https://xrdcif.com`. Running `doctor` without a key self-checks connectivity and prints registration guidance; 401 responses include the same guidance.

Each account gets a fixed daily free quota that resets on a UTC day boundary and never accumulates. Once the free quota and paid credit balance are exhausted, the service returns HTTP 402; the client prints the purchase link and remaining quota clearly, exits non-zero, and never fabricates or caches results. Purchases are completed on the website.

Publishing generally requires `SKILL.md` plus the `scripts/` and `references/` layout and a distributable zip. Realistically, GitHub (public repo + release zip) is the channel with no gatekeeping; Claude-style platforms use local user-installed skills, and WorkBuddy currently offers zip sharing rather than a public developer submission portal. Honest boundaries: payments are handled server-side via Paddle, same-source self-evaluation metrics must not be used as accuracy claims, and the API key is never printed or logged. The `doctor`/401 registration guidance points to `https://xrdcif.com` — that is the traffic funnel destination.
