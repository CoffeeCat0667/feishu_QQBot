"""单次运行编排（PLAN §5、§6）。

**唯一**同时 import 纯模块与 I/O 模块的文件。换实现（换 LLM、换数据源）只改这里。

固定顺序：

    拉数据 → 渲染上下文 → 算风险 → Agent 要点 → 标题 + 要点 + 风险块 → 逐条发送

失败语义（Q3/Q4 默认）：
  - 前置阶段（fetch / render / analyze / agent）任一失败 → StageError，
    **一条业务消息都不发**，只上报管理员；
  - 发送阶段单条失败 → 重试后跳过，继续发下一条，最后汇总。
"""

from __future__ import annotations

import datetime as _dt
from typing import Callable

from models import Deps, OutMessage, RunReport, StageError

import analysis
import blocks
import render
import splitter


def collect(cfg: object, deps: Deps, now: _dt.datetime) -> tuple[list[OutMessage], RunReport]:
    """产出待发消息，不发送。后续版本的 `--dry-run` 直接复用这一步（Q13）。

    TODO M2/M4：
      1. snapshot = deps.source.fetch(cfg.feishu)
      2. ctx = render.render(snapshot, cfg.feishu)
      3. report = analysis.analyze(snapshot, cfg.feishu.task_table_name,
                                    cfg.risk, deps.clock.today(), now)
      4. points = deps.agent.generate(cfg.prompt, ctx.text, report)
      5. messages = [OutMessage(title(now))]
                  + [OutMessage(t) for t in splitter.split_points(points, ...)]
                  + blocks.build(report, resolve_qq, deps.clock.today())
      6. 统计填 RunReport（不回填任何编造数字）
    """
    raise NotImplementedError("TODO M2: 编排 collect()")


def run_once(cfg: object, deps: Deps, now: _dt.datetime | None = None) -> RunReport:
    """跑一轮：collect → 逐条发送 → 返回 RunReport。

    TODO M3：按 `send.interval_ms` 间隔发送；单条失败重试 `napcat.retries` 后跳过；
    目标解析失败 → StageError（此时还一条都没发）。
    """
    raise NotImplementedError("TODO M3: 编排 run_once()")


def resolve_qq_factory(cfg: object, deps: Deps, members: list) -> Callable[[str], int | None]:
    """闭包：姓名 → QQ 号，内部走 napcat.match_member + risk.owner_aliases。"""
    raise NotImplementedError("TODO M3: QQ 解析闭包")
