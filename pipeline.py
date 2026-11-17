"""一次运行的编排：拉数据 → 上下文 → 算风险 → LLM → 拼消息 → 发送。

只有这里同时接触 I/O 和纯逻辑；改数据源/换 LLM 只改这个文件。

失败语义（Q3/Q4）：
  - 前置（拉数据/渲染/算风险/LLM）失败 → 抛异常，**一条业务消息都不发**；
  - 发送阶段单条失败 → 重试后跳过，继续发下一条，最后汇总。
"""

from __future__ import annotations

import datetime as dt

import feishu
import qq
import report

INTERVAL_MS = 1500
SEND_RETRIES = 3


def run_once(cfg: dict, now: dt.datetime) -> dict:
    """跑一轮，返回汇总 dict（字段就这 6 个，别再扩）：

        {"tables": 11, "rows": 159, "chars": 39504,
         "points": 4, "sent": 9, "failed": 0, "unmatched": ["陈勇", ...]}
    """
    raise NotImplementedError("TODO M3: run_once()")


def build_messages(cfg: dict, now: dt.datetime) -> tuple[list[dict], dict]:
    """产出待发消息 + 统计，不发送。

        [{"text": "11 月 17 日 进展通报", "at": None},
         {"text": "24 条任务已完成……", "at": None},
         {"text": "的进度风险：\\n底盘拼装（…）", "at": 123456}]

    TODO M2/M3：
      1. tables = feishu.fetch(cfg)
      2. context = report.render_context(tables)
      3. tasks = report.parse_tasks(tables, cfg["feishu"]["task_table"])
      4. rows, stats = report.analyze(tasks, today, now, near, idle)
      5. points = ask_llm(cfg, context, stats)
      6. 消息 = 标题 + 分条后的要点 + 每人风险块（一人一条）
    """
    raise NotImplementedError("TODO M3: 拼消息")


def ask_llm(cfg: dict, context: str, stats: dict) -> list[str]:
    """smolagents 跑一次，返回 3~6 条要点。

    TODO M4：
      - instructions = persona + style + output_format；
      - 输入 = task_hint + 表格上下文 + **代码算好的统计**（数字不交给模型数）；
      - `ToolCallingAgent(tools=[], model=..., max_steps=1, verbosity_level=ERROR)`；
      - `OpenAIModel` / `OpenAIServerModel` 两个名字都试（T5）；
      - 少于 2 条 → RuntimeError（§6）。
    """
    raise NotImplementedError("TODO M4: 调 LLM")


def send_all(cfg: dict, messages: list[dict]) -> tuple[int, int]:
    """逐条发送，间隔 1.5s；单条失败重试 3 次后跳过。返回 (成功, 失败)。"""
    raise NotImplementedError("TODO M3: 批量发送")
