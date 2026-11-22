# XRD↔CIF 晶体检索 Skill

[English](README.md) · [在线服务](https://xrdcif.com)

[![skills.sh](https://skills.sh/b/xrdcif/xrdcif)](https://skills.sh/xrdcif/xrdcif)

**让你的 AI 助手从一条粉末 XRD 衍射谱鉴定晶体物相——拿到排序后的 CIF 候选结构，附带可追溯的物理规则证据，而不是黑箱猜测。**

这是一个即装即用的 Skill，适用于 [WorkBuddy](https://www.workbuddy.cn/)、Claude 及任何其他支持 `SKILL.md` 规范的智能体。它封装了 [xrdcif.com](https://xrdcif.com) 的免费 XRD↔CIF 跨模态检索服务：输入衍射谱，返回 Top-K 候选晶体结构，每个候选都经教材抽取的物理规则独立复核，标注 `SUPPORT`（支持）/ `CONTRADICT`（矛盾）/ `INSUFFICIENT`（证据不足）。客户端是纯 Python 标准库——零第三方依赖，任何机器都能跑。

> Skill 本身免费开源，它只是一个客户端：检索、额度与支付都在网站侧完成。注册即赠免费额度，先试后付。

---

## 为什么你需要它

做粉末衍射的人都知道流程有多繁琐：拿峰位去比对 PDF 卡片、逐个核对候选结构、手工验算晶格参数。这个 Skill 把整套循环变成跟助手的一次对话：

- **物相鉴定**——"这是我的 2θ/强度峰表，可能是什么结构？"
- **峰位解释**——某条衍射谱与什么相符。
- **结构反查**——"给出这个 CIF 结构的理论衍射谱。"
- **有证据，不只是答案**——每个候选都带三态物理复核（`SUPPORT` / `CONTRADICT` / `INSUFFICIENT`），以及可查阅的 `verification` / `render` 记录。

它跑在你的助手里，不用在网页表单和工作区之间来回切。

---

## 三步上手

### 1. 安装 Skill

**推荐——用 skills CLI 一条命令安装**（适用于 Claude Code、Cursor、Windsurf 及任何遵循 `SKILL.md` 规范的智能体）：

```bash
npx skills add https://github.com/xrdcif/xrdcif --skill xrd-cif-retrieval
```

**或手动安装。** 把 `skills/xrd-cif-retrieval/` 目录复制到你所用智能体的用户级 skills 目录，保持目录名不变：

| 平台 | 用户级 skills 目录 |
|---|---|
| WorkBuddy | `~/.workbuddy/skills/xrd-cif-retrieval/` |
| Claude / 其他支持 `SKILL.md` 的智能体 | 该平台官方文档规定的用户 skills 路径 |

无需构建。客户端只需要 Python 3（标准库）。

### 2. 获取免费 API Key

1. 在 **[https://xrdcif.com](https://xrdcif.com)** 注册（注册即赠额度 + 每日免费额度）。
2. 确认邮箱。
3. 进入 **账户与额度 → 开发者** 栏目，生成 API Key。
4. 设置环境变量：

```bash
export XRD_API_KEY=xrdk_xxx          # Windows PowerShell: $env:XRD_API_KEY="xrdk_xxx"
```

### 3. 直接跟助手说

用自然语言提问即可——比如"用 XRD-CIF skill 帮我鉴定这条谱：31.70 100, 45.45 55, 56.55 20 ..."。若未配置 Key，Skill 会先跑 `doctor` 自检并给出注册引导，不会卡死。

也可以直接在 Skill 目录调用命令行：

```bash
python scripts/xrd_client.py doctor     # 自检（无 Key 时打印注册引导）
python scripts/xrd_client.py quota      # 当日免费额度 + 余额 + 购买链接
python scripts/xrd_client.py search --k 5
```

---

## 能做什么

| 命令 | 用途 | 说明 |
|---|---|---|
| `doctor` | 连通性 + Key 检查 | 无 Key 时打印注册引导，不是死路一条 |
| `quota` | 当日免费额度、余额、购买链接 | 只读，不扣费 |
| `search` | 衍射谱 → Top-K CIF 候选 | 支持 `simulate` / `peaks` / `xy` 三种输入 |
| `reverse` | CIF 结构 → 理论衍射谱 | 快速结构反查 |
| `history` | 完整结果 + 逐候选证据 | 含 `verification` / `render` 追溯记录 |
| `account` | 账户、余额、账本摘要 | — |

`search` 的输入模式：

- `simulate`——内置演示结构（默认 `NaCl-rocksalt`），零配置；
- `peaks`——2θ / 相对强度峰表文件（`--peaks-file`）；
- `xy`——连续谱文件（`--xy-file`）。

所有子命令支持 `--json`（输出原始 JSON）和 `--timeout`。所有失败路径返回非零退出码，客户端绝不静默失败。

---

## 额度与付费

- 注册即赠额度，另有**固定每日免费额度**，按 UTC 00:00 重置，不累积。
- 先扣当日免费额度，再扣付费余额。
- 两者都耗尽时服务返回 **HTTP 402**；客户端打印服务端给出的购买链接与剩余额度后停止。**绝不伪造或缓存结果。**
- 支付在网站侧经 Paddle 完成。Skill 与客户端不接触支付凭据，也不写死购买链接——链接始终由服务端返回。

---

## 诚实边界

这些话我们宁可先说清楚，也不想让你事后才发现：

- **自评是同源的。** 候选库与仿真谱来自同一物理引擎、同一批内置结构。网站上的 Recall/AUC 是回归自检，**不能当作泛化准确率引用**——请勿作为性能指标对外宣称。
- **库规模现状。** 当前服务内置 27 个结构的演示库与 27 条实测谱参考；COD 全量数据接入进行中。结果是科研辅助，不是权威物相鉴定结论。
- **三态复核是规则驱动的。** `SUPPORT` / `CONTRADICT` / `INSUFFICIENT` 来自教材抽取的物理规则，是独立交叉核对，不构成鉴定准确率的保证。
- **关键结论请自行复核。** 用于正式发表前，务必以原始文献或标准数据库交叉验证。

---

## 运行环境

- Python 3.x（仅标准库——`urllib`，无需 pip 安装）
- 一个来自 [xrdcif.com](https://xrdcif.com) 的 API Key（免费注册）
- 支持 `SKILL.md` 的智能体，或直接使用命令行

## 给 Skill 目录维护者

本仓库采用 [skills.sh](https://skills.sh) 与 `npx skills` CLI 约定的目录结构：`skills/` 下一 skill 一目录，每个目录含 `SKILL.md`。CLI 会自动发现 `skills/xrd-cif-retrieval/SKILL.md`，无需向任何注册表提交表单。目录榜单由 `npx skills add` 的匿名安装遥测驱动，因此要上榜必须有真实用户安装。

## 链接

- 服务与免费注册：**[https://xrdcif.com](https://xrdcif.com)**
- 定价页：[https://xrdcif.com/pricing](https://xrdcif.com/pricing)
- API 契约：[`skills/xrd-cif-retrieval/references/api.md`](skills/xrd-cif-retrieval/references/api.md)

---

本 Skill 用于科研与教育目的。服务条款、退款政策与隐私说明见服务网站。
