"""数据模型与接口契约。

纯模块：只依赖标准库，不 import 任何业务模块、不做 I/O。
所有跨模块传递的结构都在这里定义，避免模块之间互相 import 形成环。

依赖方向：models ← 其它所有模块（它自己谁都不 import）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol, Sequence


# --------------------------------------------------------------------------
# 原始数据（飞书 → 内存，不落盘）
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TableData:
    """一张飞书表的原样快照。records 是接口返回的 dict，保持原样。"""

    table_id: str
    name: str
    field_names: tuple[str, ...]
    records: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class Snapshot:
    """一次拉取的全部表。只在内存中存在。"""

    fetched_at: datetime
    tables: tuple[TableData, ...]

    @property
    def row_count(self) -> int:
        """所有表加起来的行数。"""
        raise NotImplementedError("TODO M2: 统计行数")


# --------------------------------------------------------------------------
# 归一化后的任务（analysis / blocks / render 共用）
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Task:
    """一条研发任务，字段已归一化（优先级去掉括号说明、进度转成 0~1 的 float）。"""

    record_id: str
    task_id: str
    name: str
    owner: str
    status: str                      # 待开始 / 进行中 / 待评审 / 已完成 / 阻塞
    priority: str                    # P0 / P1 / P2 / P3（缺省为空串）
    group: str                       # 职能组：算法 / 电控 / 机械 / 运营
    due: date | None                 # 预计完成日
    progress: float | None           # 0~1，解析失败为 None
    last_update: datetime | None     # 最后更新时间
    note: str = ""                   # 今日进展（供 Agent 参考）


@dataclass(frozen=True)
class RiskItem:
    """进入危险块的一条任务，天数已算好。"""

    task: Task
    days: int        # due - today：负数=已逾期天数，0..near_days=剩余天数
    kind: str        # "overdue" | "near"


@dataclass(frozen=True)
class OwnerRisk:
    """一个负责人的风险聚合。排版留给 blocks.py，这里只有数据。"""

    owner: str
    qq: int | None
    overdue: tuple[RiskItem, ...]
    near: tuple[RiskItem, ...]
    idle_days: int | None            # 仅在无 overdue/near 时填（E3）
    last_update: datetime | None


@dataclass(frozen=True)
class RiskSummary:
    """给管理员汇总和 Agent 用的总量统计。"""

    total_tasks: int = 0
    done: int = 0
    blocked: int = 0
    overdue: int = 0
    near: int = 0
    no_owner: int = 0
    unmatched_qq: tuple[str, ...] = ()


@dataclass(frozen=True)
class RiskReport:
    """analysis.analyze() 的唯一产出。不含任何排版字符串。"""

    owners: tuple[OwnerRisk, ...]
    summary: RiskSummary


# --------------------------------------------------------------------------
# 消息与运行结果
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class OutMessage:
    """一条待发消息。

    text 是正文，**不含 @ 段**；at_qq 非空时由发送端在最前面插入一个 at 段。
    匹配不到 QQ 的块（D22）at_qq 为 None，姓名直接写在 text 开头。
    """

    text: str
    at_qq: int | None = None


@dataclass(frozen=True)
class SendResult:
    """发送阶段结果：成功条数 + 失败明细（不中断整轮，见 §6）。"""

    sent: int = 0
    failures: tuple[tuple[OutMessage, str], ...] = ()   # (消息, 失败原因)


@dataclass
class RunReport:
    """一次运行的最终报告，既用于管理员汇总，也用于返回值。

    刻意做成可变对象：pipeline 分阶段填充，失败时也能拿到已完成的阶段。
    """

    started_at: datetime | None = None
    finished_at: datetime | None = None
    stage: str = "init"                  # init / fetch / render / analyze / agent / send / done
    ok: bool = True
    error: str = ""
    tables: int = 0
    rows: int = 0
    context_chars: int = 0
    points: int = 0
    messages: int = 0
    sent: int = 0
    failed: int = 0
    unmatched_qq: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# 错误
# --------------------------------------------------------------------------

class StageError(RuntimeError):
    """前置阶段失败（fetch / render / analyze / agent）。

    前置失败 = 整轮一条业务消息都不发，只上报管理员（§6）。
    发送阶段的单条失败不抛这个异常，走 SendResult。
    """

    def __init__(self, stage: str, message: str, *, cause: BaseException | None = None):
        super().__init__(f"[{stage}] {message}")
        self.stage = stage
        self.cause = cause


# --------------------------------------------------------------------------
# 四个 I/O 接口（实现分别在 clock / feishu_source / agent / napcat）
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TargetSpec:
    """配置里的收件人：群或好友，name 与 id 至少给一个。"""

    type: str                     # "group" | "friend"
    name: str = ""
    id: int | None = None


@dataclass(frozen=True)
class Member:
    """群成员，用于姓名 → QQ 匹配。"""

    user_id: int
    nickname: str
    card: str = ""


@dataclass(frozen=True)
class ResolvedTarget:
    """名称解析后的发送目标。"""

    kind: str        # "group" | "friend"
    id: int
    name: str


class Clock(Protocol):
    """时间基准。永远返回带 UTC+8 时区的 datetime，与系统时区无关。"""

    def now(self) -> datetime:
        ...

    def today(self) -> date:
        ...


class DataSource(Protocol):
    """数据源。目前只有飞书；测试可塞夹具实现。"""

    def fetch(self, cfg: Any) -> Snapshot:
        ...


class Agent(Protocol):
    """LLM。只产出全局要点，不碰风险块（E1）。"""

    def generate(self, prompt: Any, context: str, risks: RiskReport) -> list[str]:
        ...


class Sender(Protocol):
    """发送端。名称解析、成员拉取、发消息三件事都归它。"""

    def resolve_target(self, spec: Any) -> ResolvedTarget:
        ...

    def members(self, group_id: int) -> list[Member]:
        ...

    def send(self, target: ResolvedTarget, message: OutMessage) -> int:
        ...


# --------------------------------------------------------------------------
# 依赖容器：pipeline / main 只认这五个字段，测试时塞假实现
# --------------------------------------------------------------------------

@dataclass
class Deps:
    """显式注入。不搞全局单例，也不需要 monkeypatch。"""

    clock: Clock
    source: DataSource
    agent: Agent
    sender: Sender
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("qqbot"))
