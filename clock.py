"""从 NTP 校时一次，并用 monotonic 推进 UTC+8 时间。"""

from __future__ import annotations

import datetime as dt
import socket
import struct

UTC8 = dt.timezone(dt.timedelta(hours=8))

NTP_SERVERS = (
    "ntp.aliyun.com",
    "ntp.tencent.com",
)
NTP_TIMEOUT = 3
NTP_EPOCH_OFFSET = 2208988800


class Clock:
    """`sync()` 之后才能用 `now()`。"""

    def __init__(self, servers: tuple[str, ...] = NTP_SERVERS) -> None:
        self._servers = servers
        self._base_epoch = 0.0
        self._base_mono = 0.0
        self.source = ""

    def sync(self) -> str:
        """依次查询 NTP 源，第一个成功就用它；全失败抛 RuntimeError。"""
        raise NotImplementedError("TODO M1: SNTP 校时")

    def now(self) -> dt.datetime:
        """UTC+8 的当前时间。未 sync 直接抛 RuntimeError。"""
        raise NotImplementedError("TODO M1: now()")

    def today(self) -> dt.date:
        raise NotImplementedError("TODO M1: today()")
