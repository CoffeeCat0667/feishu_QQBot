"""入口：CLI、主循环、触发判定、state.json、管理员日志。

    python main.py --provision   # 推送 NapCat httpServers 并回读校验
    python main.py --check       # 体检：校时 / 飞书 / NapCat / 群与成员
    python main.py --once        # 立即跑一次（真实发送）
    python main.py               # 常驻：首启跑一次，之后按 times 触发

触发判定：NTP 时间 → 落在某个 `times` 的 ±30 秒窗口内，且当天该时间点没跑过。
去重状态只记 `{日期: [已跑的时间点]}` + `last_run_at`，坏了就当空的（Q7）。

进程永不退出：任何未捕获异常 → 记日志 + 私聊管理员 → 等 30 秒继续。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
import time
from pathlib import Path

import clock as clock_mod
import config as config_mod
import pipeline
import qq

POLL_SECONDS = 5
TOLERANCE_SECONDS = 30
RETRY_AFTER_ERROR = 30
MAX_MSG = 800

LOG = logging.getLogger("qqbot")


# --------------------------------------------------------------------------
# state.json —— 只回答一个问题：今天这个时间点跑过没有
# --------------------------------------------------------------------------

def read_state(path: str | Path) -> dict:
    """读不到/损坏 → `{"fired": {}, "last_run_at": ""}` + WARNING。"""
    raise NotImplementedError("TODO M1: 读 state")


def write_state(path: str | Path, state: dict) -> None:
    """先写 `.tmp` 再 `os.replace`，断电不会留下半个 JSON。"""
    raise NotImplementedError("TODO M1: 写 state")


def due_slot(times: list[str], now: dt.datetime, state: dict) -> str | None:
    """命中则返回该时间点标签（如 "09:00"），否则 None。

    TODO M1：环形距离 `d = min(|now_sod - slot|, 86400 - d)`，`d <= 30` 算命中；
    去重键是 (今天, 标签)。
    """
    raise NotImplementedError("TODO M1: 触发判定")


# --------------------------------------------------------------------------
# 日志与管理员
# --------------------------------------------------------------------------

def setup_logging(level: str = "INFO") -> None:
    """stderr 输出，格式 `HH:MM:SS LEVEL message`。不要接管第三方库的 INFO。"""
    raise NotImplementedError("TODO M5: 日志初始化")


def send_admin(cfg: dict, text: str) -> None:
    """私聊管理员。失败只写 stderr，绝不递归上报（§5.10）。"""
    raise NotImplementedError("TODO M5: 私聊管理员")


def summarize(result: dict, elapsed: float) -> str:
    """一次运行的汇总文本（就 5 行，别加第 6 行）。"""
    raise NotImplementedError("TODO M5: 汇总文本")


# --------------------------------------------------------------------------
# 子命令
# --------------------------------------------------------------------------

def cmd_check(cfg: dict) -> int:
    """体检输出：

        [校时] ntp://ntp.aliyun.com  UTC+8=2026-11-17 13:22:32
        [飞书] 11 张表 / 159 行 / 39,504 字
        [NapCat] 2108205515 肥肥的大蓝鱼
        [目标] 大肥鱼测试 -> 727456069
        [成员匹配] 3 人；负责人 24 个中匹配到 2 个
    """
    raise NotImplementedError("TODO M1: --check")


def cmd_provision(cfg: dict) -> int:
    raise NotImplementedError("TODO M1: --provision")


def run_and_report(cfg: dict, clk: clock_mod.Clock) -> bool:
    """跑一轮 + 汇总上报。前置失败时也上报 ERROR，不抛给调用方。"""
    raise NotImplementedError("TODO M3: 跑一轮并上报")


def service(cfg: dict) -> int:
    """常驻主循环。首启立即跑一次（D9），之后每 5 秒看一次表。"""
    raise NotImplementedError("TODO M1: 主循环")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="main.py", description="QQ 定时进展通报机器人")
    p.add_argument("--config", default="config.json")
    p.add_argument("--provision", action="store_true", help="推送 NapCat httpServers")
    p.add_argument("--check", action="store_true", help="体检")
    p.add_argument("--once", action="store_true", help="立即跑一次（真实发送）")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = config_mod.load(os.environ.get("QQBOT_CONFIG", args.config))
    setup_logging()

    if args.provision:
        return cmd_provision(cfg)
    if args.check:
        return cmd_check(cfg)
    if args.once:
        clk = clock_mod.Clock()
        clk.sync()
        return 0 if run_and_report(cfg, clk) else 1
    return service(cfg)


if __name__ == "__main__":
    sys.exit(main())
