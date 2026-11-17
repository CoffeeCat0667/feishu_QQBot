"""触发判定与当日去重（PLAN §5.2）。

判定是纯逻辑；去重状态落盘在 `state.json`（Q5/Q6/Q7 的默认），
所以本模块只有 `StateStore` 一个类碰文件，其余函数保持纯函数。

环形距离：`d = min(|now_sod - target_sod|, 86400 - d)`，兼容跨零点。
去重键：(时间点标签 "09:00", 触发点所属日期)。
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Trigger:
    """本次要触发的时间点。"""

    label: str                  # 配置里的原样写法，如 "09:00"
    occurrence: _dt.date        # 这个时间点属于哪一天（UTC+8）


def parse_time_of_day(label: str) -> int:
    """`"09:00"` / `"18:00:30"` → 当天秒数。格式错误抛 ValueError。"""
    raise NotImplementedError("TODO M1: 解析 HH:MM[:SS]")


def seconds_of_day(now: _dt.datetime) -> int:
    """UTC+8 的当天秒数。"""
    raise NotImplementedError("TODO M1: 计算 sod")


def occurrence_date(now: _dt.datetime, target_sod: int) -> _dt.date:
    """触发点所属日期：now + (target_sod - now_sod)，用环形距离取最近的一侧。

    TODO M1：00:00 附近不能让 23:59 的触发算到第二天。
    """
    raise NotImplementedError("TODO M1: 反推触发日期")


def find_due(
    now: _dt.datetime,
    times: tuple[str, ...],
    tolerance_seconds: int,
    fired: object,
) -> Trigger | None:
    """在容差窗口内、且今天还没触发过的时间点里挑一个。

    TODO M1：多个同时命中时取最接近的一个；其余记录 WARNING 并标记已执行，
    避免一次运行堆积两次发送（§5.2）。
    """
    raise NotImplementedError("TODO M1: find_due()")


# --------------------------------------------------------------------------
# 去重状态
# --------------------------------------------------------------------------

@dataclass
class StateStore:
    """`state.json` 的读写。结构：

    ```json
    {"version": 1,
     "fired": {"2026-11-17": ["09:00"]},
     "last_run_at": "2026-11-17T09:00:03+08:00"}
    ```

    - 只保留最近 `keep_days` 天的 fired 记录，避免无限增长；
    - 文件不存在 → 空状态；
    - 文件损坏/被截断 → 空状态 + WARNING，继续跑（Q7 默认）。
    """

    path: Path = Path("state.json")
    keep_days: int = 7
    _data: dict = field(default_factory=dict, repr=False)

    def load(self) -> "StateStore":
        raise NotImplementedError("TODO M1: 读 state.json")

    def save(self) -> None:
        """先写临时文件再 `os.replace`，避免断电留下半个 JSON。"""
        raise NotImplementedError("TODO M1: 原子写 state.json")

    def is_fired(self, label: str, occurrence: _dt.date) -> bool:
        raise NotImplementedError("TODO M1: 查询去重键")

    def mark_fired(self, label: str, occurrence: _dt.date, when: _dt.datetime) -> None:
        """记一笔并刷新 `last_run_at`（Q6）。"""
        raise NotImplementedError("TODO M1: 记录去重键")

    def suppress(self, now: _dt.datetime, seconds: int) -> None:
        """手动跑后压住窗口，避免 09:00 前后重复发（§5.2）。"""
        raise NotImplementedError("TODO M1: 抑制窗口")
