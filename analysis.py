"""任务归一化 + 负责人聚合 + 危险判定（PLAN §5.5）。

纯模块：输入 Snapshot + 配置 + 今天的日期，输出 RiskReport。
这里**只算数，不排版**——任何给人看的字符串都在 blocks.py。

判定口径：
  未完成 = 任务状态 != "已完成"（空状态按未完成处理并记 WARNING）
  超期   = 未完成 且 due < today             （用 .date() 比较，毫秒对齐午夜）
  临近   = 未完成 且 0 <= (due - today).days <= near_days
  久未更新 = max(最后更新时间) < now - idle_days
  入列   = 有超期 或 有临近 或 久未更新；有前两者时不再追加「无更新」（E3）

实测坑：
  - `进度百分比` 是 `"0.21"` / `"0.8"` / `"1"` 这种 0~1 的**字符串**；
  - 24 条「已完成」的 `实际完成日` 全为空 → 只能按状态判未完成；
  - `算法 顾子奕 小登` 是一个人的姓名，**绝不按空格切**。
"""

from __future__ import annotations

import datetime as _dt

from models import OwnerRisk, RiskItem, RiskReport, RiskSummary, Snapshot, Task

DONE = "已完成"


# --------------------------------------------------------------------------
# 单元格 → 值
# --------------------------------------------------------------------------

def cell_ts(value: object, tz: _dt.tzinfo) -> _dt.datetime | None:
    """毫秒时间戳（或秒）→ 带时区 datetime；空/非法返回 None。"""
    raise NotImplementedError("TODO M1: 时间戳解析")


def cell_date(value: object, tz: _dt.tzinfo) -> _dt.date | None:
    raise NotImplementedError("TODO M1: 日期解析")


def cell_progress(value: object) -> float | None:
    """`"0.21"` → 0.21；`">1"` 的值（若有）按百分数/100 处理；解析失败返回 None。"""
    raise NotImplementedError("TODO M1: 进度解析")


def cell_priority(value: object) -> str:
    """`"P1（影响里程碑）"` → `"P1"`。"""
    raise NotImplementedError("TODO M1: 优先级归一化")


def cell_owner(value: object) -> str:
    """人员字段 → 姓名。list 取每项 name；dict 取 name；str 原样 strip，不按空格切。"""
    raise NotImplementedError("TODO M1: 负责人解析")


def parse_task(record: dict, tz: _dt.tzinfo) -> Task | None:
    """一条原始 record → Task。缺关键字段时返回 None 并计入告警。"""
    raise NotImplementedError("TODO M1: record → Task")


# --------------------------------------------------------------------------
# 判定
# --------------------------------------------------------------------------

def analyze(
    snapshot: Snapshot,
    task_table_name: str,
    risk_cfg: object,
    today: _dt.date,
    now: _dt.datetime,
) -> RiskReport:
    """全表 → 风险报告。

    TODO M1：
      1. 只取 `task_table_name` 对应的表（其它表只进上下文，不参与判定）；
      2. parse_task 全量转换；
      3. 按负责人分桶，算 overdue / near / idle_days；
      4. 块内排序：优先级 P0→P3 → 逾期天数降序 → 姓名（D27）；
      5. 负责人排序：最早截止日升序 → 姓名（E3 之后仍成立）；
      6. RiskSummary 里带 total/done/blocked/overdue/near/no_owner。
    """
    raise NotImplementedError("TODO M1: 危险判定")


def summarize(tasks: list[Task], today: _dt.date, near_days: int) -> RiskSummary:
    raise NotImplementedError("TODO M1: 总量统计")
