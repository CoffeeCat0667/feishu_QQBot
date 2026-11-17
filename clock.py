"""时间基准：NTP 主、HTTP `Date` 兜底、系统时钟兜底。

I/O 模块（只碰网络），但对外只暴露 Clock 接口（models.Clock）。

关键设计（PLAN §5.1）：
  - 基准用 monotonic() 推进，系统时钟被改也不会让触发点漂移；
  - now() 永远返回带 UTC+8 时区的 datetime，与服务器本地时区无关。
"""

from __future__ import annotations

import datetime as _dt

from models import Clock


UTC8 = _dt.timezone(_dt.timedelta(hours=8))


class NtpClock(Clock):
    """SNTP 校时 + monotonic 推进。

    TODO M1：
      1. `socket` + `struct` 手写 SNTP（零依赖），UDP 123，超时 `ntp_timeout_seconds`；
      2. 校验 stratum != 0、长度 ≥ 48、transmit 时间戳非 0（防 Kiss-o'-Death）；
      3. 依次尝试 `ntp_servers`，全失败 → HTTP `Date` 响应头；
      4. 记录 `base_epoch` 与 `base_monotonic`，之后按 monotonic 推算；
      5. 每 `resync_minutes` 重校一次，|offset| > 1s 打日志。
    """

    def __init__(self, time_sync: object) -> None:
        self._cfg = time_sync
        self._base_epoch: float = 0.0
        self._base_monotonic: float = 0.0
        self._source: str = "unset"

    # ---- Clock 接口 -----------------------------------------------------

    def now(self) -> _dt.datetime:
        raise NotImplementedError("TODO M1: now()")

    def today(self) -> _dt.date:
        raise NotImplementedError("TODO M1: today()")

    # ---- 内部 -----------------------------------------------------------

    def resync(self) -> float:
        """重新校时，返回本次 offset（秒）。失败抛 StageError("clock", ...)。"""
        raise NotImplementedError("TODO M1: resync()")

    @property
    def source(self) -> str:
        """本次基准来自哪里：`ntp://host` / `http://...` / `system`。"""
        return self._source


class SystemClock(Clock):
    """降级实现，仅当 `time_sync.mode == "system"` 或 `on_total_failure == "system"` 时使用。"""

    def now(self) -> _dt.datetime:
        raise NotImplementedError("TODO M1: 系统时钟")

    def today(self) -> _dt.date:
        raise NotImplementedError("TODO M1: 系统时钟")


def build_clock(time_sync: object) -> Clock:
    """按配置挑一个实现。"""
    raise NotImplementedError("TODO M1: build_clock()")
