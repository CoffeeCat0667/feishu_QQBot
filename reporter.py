"""日志上报：logging.Handler → 管理员私聊（PLAN §5.10）。

I/O 模块。只有 `main` 装配它；底层模块永远不 import 本文件，只写
`logging.getLogger(__name__)`。

规则：
  - 每次运行结束发一条**汇总**；
  - ERROR 立即发，不等批量；
  - 普通日志按 `logging.batch_seconds` 合并成一条，避免刷屏；
  - 上报失败 → 熔断 60 秒，只写 stderr，绝不递归上报；
  - 发出前对 `api_key` / OneBot `token` / 飞书 `personal_base_token` 打码。
"""

from __future__ import annotations

import logging

from models import RunReport


class AdminReporter(logging.Handler):
    def __init__(self, sender: object, admin: tuple, cfg: object) -> None:
        super().__init__()
        self._sender = sender
        self._admin = admin
        self._cfg = cfg
        self._pending: list[str] = []
        self._broken_until: float = 0.0

    # ---- logging.Handler ------------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        """ERROR 立即发，其余进缓冲区等 `flush_pending()`。

        TODO M5：格式化 + 打码 + 熔断判断；`self.handleError` 兜底。
        """
        raise NotImplementedError("TODO M5: 处理日志记录")

    # ---- 对外 -----------------------------------------------------------

    def flush_pending(self) -> None:
        """把缓冲区合并成一条消息发出去（超过 max_chars_per_report 时截断）。"""
        raise NotImplementedError("TODO M5: 批量发送")

    def report_run(self, report: RunReport) -> None:
        """一次运行的汇总，格式见 §5.10：

            [进展通报] 2026-11-17 18:00:02 完成
            表格 11 张 / 159 行 / 上下文 39,504 字
            Agent 用时 42.3s / token 26,431 / 要点 4 条
            发送 4 条正文 + 9 条 @ 块，失败 0
            未匹配 QQ：〈姓名、姓名 …〉共 N 人
        """
        raise NotImplementedError("TODO M5: 运行汇总")

    def _send(self, text: str) -> bool:
        """真正发一条私聊；失败熔断 60 秒并返回 False。"""
        raise NotImplementedError("TODO M5: 发送日志")
