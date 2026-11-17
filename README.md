[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-skeleton-yellow.svg)]()
[![OneBot](https://img.shields.io/badge/OneBot-v11-ff69b4.svg)](https://github.com/botuniverse/onebot-11)
[![NapCat](https://img.shields.io/badge/NapCat-QQ-blueviolet.svg)](https://github.com/NapNeko/NapCatQQ)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey.svg)]()
[![Last commit](https://img.shields.io/github/last-commit/CoffeeCat0667/feishu_QQBot.svg)](https://github.com/CoffeeCat0667/feishu_QQBot)

# feishu_QQBot

定时把**飞书多维表格**的项目数据拉进内存，交给 LLM 生成一段**进展通报**，再通过 **NapCat（OneBot v11）** 分条发送到 QQ 群；同时把运行日志私聊给管理员。

> **状态：骨架阶段。** 模块划分、接口契约与文档已就位，函数体为 `NotImplementedError`
> （标注了所属里程碑 M1–M5），实现按里程碑逐步补齐。
> 设计文档 `PLAN.md`、真实配置 `config.json` 与 `ThirdParty/` 均被 `.gitignore` 排除。

---

## 特性

- **NTP 校时**：触发时间取自 NTP 网络时间，不依赖系统时区。
- **内存导出**：飞书全表读进内存后直接组装上下文，**不落盘**。
- **定时触发**：以 `config.json` 中的 UTC+8 时间数组为基准，误差窗口 ±30 秒，每个时间点每天只触发一次。
- **LLM 生成**：人设、语气、条数、格式全部由配置驱动，不写死在代码里。
- **风险分块 @**：按负责人聚合超期 / 临近 / 久未更新任务，一人一条消息，块首直接 `@`。
- **日志上报**：每次运行一条汇总，错误即时上报给管理员；NapCat 不可用时熔断，避免上报风暴。
- **不读群消息**：v0.1 只发不收，群消息监听留作后续版本。

---

## 工作原理

```mermaid
flowchart LR
    NTP[NTP 服务器] --> CLOCK[clock<br/>UTC+8 时间基准]
    CLOCK --> SCH[scheduler<br/>±30s 触发判定]
    SCH --> FS[feishu_source<br/>全表读入内存]
    FS --> REN[render<br/>表格 → Markdown 上下文]
    FS --> ANA[analysis<br/>超期 / 临近 / 久未更新]
    REN --> AG[agent<br/>LLM 生成要点]
    ANA --> BLK[风险块生成<br/>代码计算，不经 LLM]
    AG --> SPL[splitter<br/>分条 + 压平 Markdown]
    BLK --> SPL
    SPL --> NC[napcat<br/>OneBot HTTP]
    NC --> QQ[QQ 群]
    NC --> ADMIN[管理员私聊]
```

顺序固定：**标题 → 全局要点 → 按人 @ 块**。

### 代码结构

代码文件平铺在仓库根目录，**没有包目录**：

| 文件 | 职责 |
|---|---|
| `main.py` | CLI、主循环、触发判定、`state.json` 去重、管理员日志 |
| `pipeline.py` | 编排一次运行：拉数据 → 上下文 → 风险 → LLM → 拼消息 → 发送 |
| `report.py` | 纯函数：渲染上下文、任务归一化、风险判定、消息文本、分条 |
| `qq.py` | OneBot 调用、名称解析、成员匹配、推送 `httpServers` |
| `feishu.py` | 飞书全表读入内存（复用 `ThirdParty/`，不落盘） |
| `config.py` | JSON → dict，默认值 + 必填校验（12 项） |
| `clock.py` | SNTP 校时 + `monotonic` 推进 |

> 当前是**骨架**：契约与签名齐备，函数体为 `NotImplementedError`（标注里程碑）。
> 数据在模块间用 dict / list 传递，没有 dataclass 层、没有 Protocol、没有依赖注入容器。

---

## 消息形态

第一条是日期标题，随后是 3~6 条要点，最后是每人一条风险块：

```text
2026 年 1 月 1 日 进展通报

⟨要点 1，20~60 字，可点名任务与数字⟩
⟨要点 2⟩
⟨要点 3⟩
...

@⟨负责人⟩ 的进度风险：
⟨任务名⟩（⟨状态⟩，预计 ⟨日期⟩，已逾期 ⟨N⟩ 天，进度 ⟨xx⟩%，⟨优先级⟩，⟨职能组⟩）
⟨任务名⟩（⟨状态⟩，预计 ⟨日期⟩，还剩 ⟨N⟩ 天，⟨优先级⟩，⟨职能组⟩）
```

- 空字段直接省略，不写「无」。
- 同一个人内部按 **优先级 P0→P3 → 逾期天数降序** 排列。
- 匹配不到 QQ 的负责人照常发送，只是不会被真正 `@` 到。

---

## 快速开始

### 1. 依赖

- Python **3.10+**（`smolagents` 要求）
- [NapCatQQ](https://github.com/NapNeko/NapCatQQ) 已登录，且开启 **OneBot HTTP** 服务
- 一份可读的飞书多维表格（需要 `app_token` 与 `personal_base_token`）

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp config_example.json config.json
```

然后填写 `config.json` 中的必填项：

| 字段 | 说明 |
|---|---|
| `times` | 触发时间数组（UTC+8），如 `["09:00", "18:00"]` |
| `state_path` | 去重状态文件，默认 `state.json` |
| `napcat.api` | 程序连 NapCat 的地址（同机 `127.0.0.1:3000`，跨机填对方 IP） |
| `napcat.token` | OneBot HTTP 鉴权 token，自己生成一串随机值 |
| `target.group` | 目标群，群名或群号 |
| `admin` | 管理员 QQ 号（收运行日志） |
| `feishu.config_path` | 飞书导出配置的路径（含 `personal_base_token`，**不要提交**） |
| `feishu.task_table` | 判定风险用的任务表名，默认 `研发进展总表` |
| `llm.api_key` / `base_url` / `model` | 任意 OpenAI 兼容接口 |
| `prompt.*` | 人设、语气、输出格式、任务提示 |
| `risk.near_days` / `idle_days` / `aliases` | 临近天数、久未更新天数、姓名→QQ 手工映射 |

> 其余参数（30 秒容差、5 秒轮询、单条 800 字、重试次数）都是代码里的常量，不进配置。
> `config.json` 已在 `.gitignore` 中。

### 3. NapCat 端

在 NapCat 中启用 OneBot HTTP 服务，并将其地址和 token 填入 `config.json` 的 `napcat.api` 与 `napcat.token`。配置检查命令：

```bash
python main.py --check
```

### 4. 运行（规划中的命令）

```bash
python main.py            # 常驻：首次启动先跑一次，之后按时间表触发
python main.py --once     # 立即跑一次（真实发送）
python main.py --check    # 体检
python -m unittest        # 无网络自测（纯函数模块）
```

> 0.1 没有 `--dry-run`，空跑请直接调 `pipeline.build_messages()`。

> 代码文件**平铺在仓库根目录**，没有包目录，所以入口是 `python main.py`，
> 不是 `python -m qqbot`。

---

## 配置结构

```text
config.json
├── times          触发时间（UTC+8），如 ["09:00", "18:00"]
├── state_path     去重状态文件路径
├── napcat         api / token
├── target         目标群（群名或群号）
├── admin          管理员 QQ（收运行日志）
├── feishu         导出配置路径、任务表名
├── llm            api_key / base_url / model / temperature / max_tokens
├── prompt         persona / style / output_format / task_hint
└── risk           near_days / idle_days / aliases
```

完整的字段说明与默认值见 [`config_example.json`](config_example.json)。

---

## 风险判定口径

| 概念 | 定义 |
|---|---|
| 未完成 | `任务状态 ≠ 已完成` |
| 超期 | 未完成且 `预计完成日 < 今天`（UTC+8） |
| 临近 | 未完成且 `0 ≤ 距截止天数 ≤ near_days` |
| 久未更新 | 该负责人所有任务中 `max(最后更新时间)` 超过 `idle_days` |
| 入列条件 | 以上任一命中；已有超期/临近的人不再重复输出「无更新」行 |

---

## 第三方依赖

本仓库**不包含**以下内容，需要自行准备：

| 项目 | 用途 | 说明 |
|---|---|---|
| `ThirdParty/feishu_export/` | 飞书多维表格导出 | 内含 `personal_base_token`，属于密钥，不入库 |
| `ThirdParty/NapCatQQ/` | QQ 协议端 | 独立部署，通过 OneBot HTTP 与本程序通信 |
| `ThirdParty/smolagents/` | Agent 框架 | 也可直接 `pip install smolagents` |

---

## 安全须知

- `config.json`、`PLAN.md`、`ThirdParty/` 均在 `.gitignore` 中，请勿用 `git add -f` 强制提交。
- 日志中会对 `api_key`、OneBot `token`、飞书 `personal_base_token` 打码。
- 若把 OneBot HTTP 绑定在 `0.0.0.0`，请务必设置非空 token，并保证端口不暴露到公网。
- 飞书的 `personal_base_token` 权限等同于文档所有者，泄露后请立即在飞书后台重置。

---

## 里程碑

| 阶段 | 内容 | 状态 |
|---|---|---|
| M1 | 配置、校时、触发、渲染、分条 | 规划中 |
| M2 | 飞书数据通路（纯内存） | 规划中 |
| M3 | NapCat OneBot HTTP 收发 | 规划中 |
| M4 | Agent 生成与流水线编排 | 规划中 |
| M5 | 日志上报与常驻部署 | 规划中 |

---

## 许可证

本项目基于 [MIT License](LICENSE) 开源。
