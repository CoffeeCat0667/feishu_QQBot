"""Agent：把全表上下文写成 3~6 条全局要点（PLAN §5.6）。

I/O 模块。只负责「怎么说」；「是什么」全部来自代码（数字、任务名、天数）。

输入 = persona/style/output_format/task_hint + 表格上下文 + **代码算好的风险清单**；
输出 = 若干条要点（不带序号、不带项目符号），交给 splitter 分条。

smolagents 1.26 用法（服务器已装）：
    ToolCallingAgent(
        tools=[],
        model=OpenAIModel(model_id=..., api_base=..., api_key=...),   # 或 OpenAIServerModel
        instructions=<persona + style + output_format>,
        max_steps=1,
        verbosity_level=LogLevel.ERROR,
    )

坑（T5）：1.26 PyPI 与 1.27.dev 的模型类命名不同 → 两个都试。
"""

from __future__ import annotations

from models import Agent, RiskReport, StageError


class SmolAgent(Agent):
    def __init__(self, llm_cfg: object) -> None:
        self._cfg = llm_cfg
        self._agent = None

    def generate(self, prompt: object, context: str, risks: RiskReport) -> list[str]:
        """跑一次推理，返回要点列表。

        TODO M4：
          1. 懒加载 smolagents（import 失败 → StageError("agent", ...)）；
          2. instructions = build_instructions(prompt)；
          3. 任务 = build_task(prompt, context, risks)；
          4. `agent.run(task)` 拿文本 → 按行切 → 去空行 → 去序号；
          5. 少于 2 条或全空 → StageError("agent", ...)（§6）；
          6. 超时 / 429 / 5xx 按 llm.retries 重试，仍失败抛 StageError。
        """
        raise NotImplementedError("TODO M4: 调用 LLM")

    def _model(self):
        """构造 OpenAIModel / OpenAIServerModel（两者兼容）。"""
        raise NotImplementedError("TODO M4: 模型适配")


def build_instructions(prompt: object) -> str:
    """persona + style + output_format 拼成系统指令。"""
    raise NotImplementedError("TODO M4: 拼指令")


def build_task(prompt: object, context: str, risks: RiskReport) -> str:
    """task_hint + 表格上下文 + 风险清单（Q14 默认：清单也给模型）。

    风险清单用小而固定的格式给，避免模型自己数数：
        [风险] 陈勇：超期 4 条，最久 70 天；底盘拼装 阻塞 21% P1 机械
    """
    raise NotImplementedError("TODO M4: 拼任务")


def parse_points(text: str) -> list[str]:
    """模型输出 → 要点列表。去掉序号（`1.` / `-` / `•`）与空行。"""
    raise NotImplementedError("TODO M4: 输出清洗")
