"""时间基准：NTP 校时一次，之后用 monotonic 推进。

为什么不直接用 `time.time()`：系统时钟可能被 NTP/人工调整，会让触发点漂移。
为什么只校一次：进程跑一天，monotonic 漂移不到 1 秒，而容差是 30 秒。

`now()` 永远返回 **UTC+8** 带时区的 datetime，与服务器本地时区无关。
"""

from __future__ import annotations

import datetime as dt
import socket
import struct

UTC8 = dt.timezone(dt.timedelta(hours=8))

NTP_SERVERS = (
    "ntp.aliyun.com",
    "ntp.tencent.com",
    "cn.pool.ntp.org",
    "time.cloudflare.com",
    "pool.ntp.org",
)
NTP_TIMEOUT = 3
NTP_EPOCH_OFFSET = 2208988800          # 1900-01-01 → 1970-01-01


class Clock:
    """`sync()` 之后才能用 `now()`。"""

    def __init__(self, servers: tuple[str, ...] = NTP_SERVERS) -> None:
        self._servers = servers
        self._base_epoch = 0.0          # 校时得到的真实 epoch 秒
        self._base_mono = 0.0           # 校时那一刻的 monotonic
        self.source = ""                # "ntp://host" / "system"

    def sync(self) -> str:
        """依次问 NTP，第一个成功就用它；全失败抛 RuntimeError。

        TODO M1：socket + struct 手写 SNTP（零依赖）：
          - 发 48 字节请求，`0x1B` 打头；
          - 校验 len >= 48、stratum != 0、transmit 时间戳非 0（防 Kiss-o'-Death）；
          - 偏差 = ((t2-t1) + (t3-t4)) / 2，这里用返回的 transmit 时间即可；
          - 成功后记 `_base_epoch` / `_base_mono = time.monotonic()`。
        """
        raise NotImplementedError("TODO M1: SNTP 校时")

    def now(self) -> dt.datetime:
        """UTC+8 的当前时间。未 sync 直接抛 RuntimeError。"""
        raise NotImplementedError("TODO M1: now()")

    def today(self) -> dt.date:
        raise NotImplementedError("TODO M1: today()")
