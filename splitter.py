"""分条与 Markdown 压平（PLAN §5.7）。

纯模块。只处理 Agent 产出的全局要点，**不处理风险块**（风险块由 blocks.py
直接给出成品消息，见 E1）。

流程：
  1. 去 Markdown（`**` `__` 反引号、`#` 标题、`>` 引用、`- ` / `* ` 列表符、代码围栏）；
  2. 按空行切块 → 块超长按单行切 → 行仍超长按标点（。！？；，）软切 → 最后硬切；
  3. 丢弃空块；不加序号（D4）；
  4. 每条 ≤ max_chars_per_message（800）。
"""

from __future__ import annotations

SOFT_BREAKS = "。！？；，、"
FENCE = "```"


def strip_markdown(text: str) -> str:
    """压平成纯文本。保留换行，去掉标记符号。"""
    raise NotImplementedError("TODO M1: 去 Markdown")


def split_points(points: list[str], max_chars: int) -> list[str]:
    """Agent 的要点列表 → 一组可发送消息。

    一条要点正常 20~60 字，几乎不会触发切分；这里只是兜底。
    空串和纯空白项直接丢弃。
    """
    raise NotImplementedError("TODO M1: 要点分条")


def split_text(text: str, max_chars: int) -> list[str]:
    """任意长文本 → 若干不超过 max_chars 的片段（按上面的三级切分）。"""
    raise NotImplementedError("TODO M1: 长文本切分")
