"""入口：CLI + 主循环（PLAN §7、§8）。

平铺布局，直接用 `python main.py`，不是 `python -m qqbot`。

    python main.py --provision     # 推送 napcat.http_server 到 NapCat 并回读校验
    python main.py --check         # 体检：校时 / 飞书行数 / NapCat / 目标解析
    python main.py --resolve 群名   # 只做名称解析
    python main.py                 # 常驻：首启跑一次，之后按时间表触发
    python main.py --once          # 立即跑一次（真实发送）
    python main.py --config other.json

`--dry-run` 不在 0.1 范围（PLAN Q13），要空跑请用 `pipeline.collect()`。

主循环每一步都可能抛异常，但**进程绝不退出**：捕获 → ERROR 上报 → 等 30s 继续。
"""

from __future__ import annotations

import argparse
import logging
import sys

from config import Config, load_config
from models import Deps


LOG = logging.getLogger("qqbot")


# --------------------------------------------------------------------------
# 装配
# --------------------------------------------------------------------------

def build_deps(cfg: Config) -> Deps:
    """把 4 个实现塞进 Deps，并挂上 reporter。测试不用调这个函数。"""
    raise NotImplementedError("TODO M1: 依赖装配")


def setup_logging(cfg: Config, deps: Deps) -> None:
    raise NotImplementedError("TODO M5: 日志初始化")


# --------------------------------------------------------------------------
# 子命令
# --------------------------------------------------------------------------

def cmd_provision(cfg: Config, dry_run: bool = False) -> int:
    raise NotImplementedError("TODO M1: --provision")


def cmd_check(cfg: Config) -> int:
    """体检输出（§7）：

        [校时] ntp://ntp.aliyun.com  offset=+0.012s  UTC+8=2026-11-17 13:22:32
        [飞书] 11 张表 / 159 行 / 39,504 字
        [NapCat] 2108205515 肥肥的大蓝鱼  retcode=0
        [目标] group 大肥鱼测试 -> 727456069
        [管理员] friend 咖啡猫 -> 944430160
        [成员匹配] 目标群 3 人；24 个负责人中匹配到 2 个
    """
    raise NotImplementedError("TODO M1: --check")


def cmd_resolve(cfg: Config, name: str) -> int:
    raise NotImplementedError("TODO M1: --resolve")


def service(cfg: Config) -> int:
    """常驻主循环。

    TODO M1/M5：
      1. 首启按 `run_once_on_start` 立即跑一次；
      2. 每 `poll_interval_seconds` 取 `deps.clock.now()`，
         `scheduler.find_due(...)` 命中就 `pipeline.run_once(...)`；
      3. 跑完 `state_store.mark_fired(...)` + `suppress(...)`；
      4. 任何未捕获异常 → ERROR 上报 → 等 30s 继续，进程不退出。
    """
    raise NotImplementedError("TODO M1: 主循环")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py", description="QQ 定时进展通报机器人")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--provision", action="store_true", help="推送 NapCat httpServers 并回读校验")
    parser.add_argument("--check", action="store_true", help="体检：校时 / 飞书 / NapCat / 名称解析")
    parser.add_argument("--resolve", metavar="NAME", help="只做名称解析并打印")
    parser.add_argument("--once", action="store_true", help="立即跑一次后退出（真实发送）")
    parser.add_argument("--log-level", default=None, help="覆盖 config 的日志级别")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)

    if args.provision:
        return cmd_provision(cfg)
    if args.check:
        return cmd_check(cfg)
    if args.resolve:
        return cmd_resolve(cfg, args.resolve)
    if args.once:
        deps = build_deps(cfg)
        import pipeline
        report = pipeline.run_once(cfg, deps)
        return 0 if report.ok else 1
    return service(cfg)


if __name__ == "__main__":
    sys.exit(main())
