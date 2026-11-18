"""从 NTP 校时一次，并用 monotonic 推进 UTC+8 时间。"""

from __future__ import annotations

import datetime as dt
import socket
import struct
import time

UTC8 = dt.timezone(dt.timedelta(hours=8))

NTP_TIMEOUT = 3
NTP_EPOCH_OFFSET = 2208988800


class Clock:
    """`sync()` 之后才能用 `now()`。"""

    def __init__(self, servers: tuple[str, ...]) -> None:
        self._servers = servers
        self._base_epoch = 0.0
        self._base_mono: float | None = None
        self.source = ""

    def sync(self) -> str:
        """依次查询 NTP 源，第一个成功就用它；全失败抛 RuntimeError。"""
        errors = []
        for server in self._servers:
            try:
                request = b"\x1b" + bytes(47)
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                    client.settimeout(NTP_TIMEOUT)
                    client.sendto(request, (server, 123))
                    response, _ = client.recvfrom(48)

                if len(response) < 48 or response[1] == 0:
                    raise ValueError("无效的 NTP 响应")
                seconds, fraction = struct.unpack("!II", response[40:48])
                if seconds == 0:
                    raise ValueError("NTP 响应没有发送时间戳")

                self._base_epoch = seconds - NTP_EPOCH_OFFSET + fraction / 2**32
                self._base_mono = time.monotonic()
                self.source = f"ntp://{server}"
                return self.source
            except (OSError, ValueError, struct.error) as exc:
                errors.append(f"{server}: {exc}")

        raise RuntimeError("NTP 校时失败: " + "; ".join(errors))

    def now(self) -> dt.datetime:
        """UTC+8 的当前时间。未 sync 直接抛 RuntimeError。"""
        if self._base_mono is None:
            raise RuntimeError("Clock.sync() 尚未成功")
        epoch = self._base_epoch + time.monotonic() - self._base_mono
        return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).astimezone(UTC8)

    def today(self) -> dt.date:
        return self.now().date()
