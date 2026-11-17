"""标题与风险块排版（PLAN §5.9）。

纯模块：**只排版，不算数**。所有天数、日期、进度都来自 analysis 的 RiskReport。
D22：匹配不到 QQ 时不加 at 段，只写姓名，且**不标注「未匹配」**。

一条块 = 一条消息，形如：

    [at 段] 的进度风险：
    底盘拼装（阻塞，预计 2026-09-08，已逾期 70 天，进度 21%，P1，机械）
    装甲板孔为及安装空间更改（待开始，预计 2026-10-18，已逾期 30 天，P0，机械）

括号内顺序固定：状态 → 预计完成日 → 逾期/剩余天数 → 进度 → 优先级 → 职能组；
空字段整项省略（不写「无」）。
"""

from __future__ import annotations

import datetime as _dt

from models import OutMessage, OwnerRisk, RiskItem, RiskReport, Task

HEADER = " 的进度风险："          # 前面接 @ 段或姓名
IDLE_LINE = "最近 {days} 天没有任务更新（最后更新 {date}）"


def title(now: _dt.datetime) -> str:
    """首条消息的标题，代码生成、不经 LLM、不带 @（D26）。

    例：`11 月 17 日 进展通报`
    """
    raise NotImplementedError("TODO M1: 标题")


def render_line(item: RiskItem, today: _dt.date) -> str:
    """一条任务 → 一行。7 项固定顺序，空字段省略。"""
    raise NotImplementedError("TODO M1: 任务行")


def render_owner(risk: OwnerRisk, today: _dt.date) -> list[str]:
    """一个人的块：标题行 + 若干任务行 / 或一行「久未更新」。"""
    raise NotImplementedError("TODO M1: 单人块")


def build(
    report: RiskReport,
    resolve_qq: object,
    today: _dt.date,
) -> list[OutMessage]:
    """RiskReport → 一串待发消息，一人一条。

    TODO M1：
      - 顺序沿用 report.owners（analysis 已排好，不要在这里重排）；
      - `resolve_qq(owner)` 返回 int 或 None，None 时姓名写进正文；
      - 块正文合并成一条消息，不做分条（E1：结构化记录不交给 splitter）。
    """
    raise NotImplementedError("TODO M1: 风险块构建")


def day_text(days: int) -> str:
    """`-70` → `已逾期 70 天`；`3` → `还剩 3 天`；`0` → `今天到期`。"""
    raise NotImplementedError("TODO M1: 天数文案")
