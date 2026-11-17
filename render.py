"""表格 → Markdown 上下文（PLAN §5.4）。

纯模块：只做字符串拼装，不碰网络、不碰文件。

单元格处理顺序：`format_cell` 扁平化 → `|` 换成 `/` → 换行换空格 →
超过 `max_cell_chars` 截断并加 `…`。
总量超过 `max_total_chars` 时从最后一张表开始丢弃，并追加一行说明。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from models import Snapshot, TableData


@dataclass(frozen=True)
class RenderedContext:
    """送给 Agent 的表格上下文。"""

    text: str
    chars: int
    tables: int
    dropped_tables: tuple[str, ...] = ()     # 因长度被丢弃的表名
    truncated_cells: int = 0


def render_cell(value: object, max_chars: int) -> str:
    raise NotImplementedError("TODO M1: 单元格扁平化 + 截断")


def render_table(table: TableData, max_cell_chars: int) -> str:
    """单表 → Markdown 表格，首行是 `## 表名（N 条）`。

    实测样例（2026-11-17，研发进展总表 66 条）：
        ## 研发进展总表（66 条）
        | record_id | 任务ID | 任务名称 | ...
    """
    raise NotImplementedError("TODO M1: 单表渲染")


def render(snapshot: Snapshot, feishu_cfg: object) -> RenderedContext:
    """全部表 → 一段上下文。超长时从后往前丢表并返回告警。"""
    raise NotImplementedError("TODO M1: 全量渲染")
