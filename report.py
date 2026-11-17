"""飞书表 → 上下文 → 风险 → 消息正文。全是纯函数，零 I/O。

四件事，原先摊在 4 个文件里，其实共用同一份内存数据，永远一起被调用：

    render_context()  表 → Markdown（给 LLM 看）
    parse_tasks()     记录 → 任务 dict
    analyze()         任务 → 每人风险 + 总量
    render_block()    一个风险人 → 一条消息文本
    split_points()    LLM 要点 → 若干条消息

判定口径（PLAN §5.5）：
    未完成 = 状态 != "已完成"（空状态按未完成）
    超期   = 未完成 且 预计完成日 < 今天
    临近   = 未完成 且 0 <= 距截止天数 <= near_days
    久未更新 = max(最后更新时间) 距今 > idle_days
    入列   = 超期>0 或 临近>0 或 久未更新；前两者存在时不再追加「无更新」（E3，约 15 字符）

排序：块内 P0→P3 → 逾期天数降序（D27）；负责人之间最早截止日升序 → 姓名。
"""

from __future__ import annotations

import datetime as dt

DONE = "已完成"
MAX_CELL = 300                 # 单元格截断长度
MAX_TOTAL = 120000             # 上下文总长上限，超了从后往前丢表
MAX_MSG = 800                  # 单条消息字数上限

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "": 9}
TASK_FIELDS = (
    "任务ID", "任务名称", "任务负责人", "任务状态", "优先级",
    "预计完成日", "进度百分比", "职能组", "今日进展", "最后更新时间",
)


# --------------------------------------------------------------------------
# 表格 → 上下文
# --------------------------------------------------------------------------

def render_context(tables: list[dict]) -> str:
    """全部表 → 一段 Markdown。超长时从最后一张表开始丢并注明。"""
    raise NotImplementedError("TODO M2: 渲染上下文")


def format_cell(value, max_chars: int = MAX_CELL) -> str:
    """单元格扁平化：`|` → `/`、换行 → 空格、超长截断加 `…`。"""
    raise NotImplementedError("TODO M2: 单元格格式化")


# --------------------------------------------------------------------------
# 记录 → 任务
# --------------------------------------------------------------------------

def ts(value) -> dt.datetime | None:
    """毫秒时间戳 → UTC+8 datetime；空/非法返回 None。"""
    raise NotImplementedError("TODO M2: 时间戳解析")


def progress(value) -> float | None:
    """`"0.21"` → 0.21；空/非法 → None。实测是 0~1 的**字符串**。"""
    raise NotImplementedError("TODO M2: 进度解析")


def owner_name(value) -> str:
    """人员字段 → 姓名。list 取每项 name，dict 取 name，str 原样 strip。

    绝不按空格切：`算法 顾子奕 小登` 是一个人的注册名。
    """
    raise NotImplementedError("TODO M2: 负责人解析")


def parse_tasks(tables: list[dict], table_name: str) -> list[dict]:
    """取出任务表 → 归一化 dict 列表：

        {"id", "name", "owner", "status", "priority", "group",
         "due": date|None, "progress": float|None, "updated": datetime|None}
    """
    raise NotImplementedError("TODO M2: 解析任务")


# --------------------------------------------------------------------------
# 任务 → 风险
# --------------------------------------------------------------------------

def analyze(
    tasks: list[dict],
    today: dt.date,
    now: dt.datetime,
    near_days: int = 5,
    idle_days: int = 15,
) -> tuple[list[dict], dict]:
    """→ ([每人一条], 总统计)

    每人一条：
        {"owner": "陈勇", "overdue": [任务...], "near": [任务...], "idle_days": 66|None}
    总统计：
        {"total": 66, "done": 24, "blocked": 4, "overdue": 24, "near": 0}
    """
    raise NotImplementedError("TODO M2: 危险判定")


# --------------------------------------------------------------------------
# 风险 → 消息文本
# --------------------------------------------------------------------------

def title(now: dt.datetime) -> str:
    """`11 月 17 日 进展通报`"""
    raise NotImplementedError("TODO M2: 标题")


def render_block(row: dict, today: dt.date) -> list[str]:
    """一个人的块 → 行列表（第一行不含 @，@ 由 qq.py 拼）。

        ["的进度风险：",
         "底盘拼装（阻塞，预计 2026-09-08，已逾期 70 天，进度 21%，P1，机械）",
         ...]

    TODO M2：括号内固定 状态 → 预计完成日 → 逾期/剩余天数 → 进度 → 优先级 → 职能组，
    空字段整项省略；没有超期/临近时只输出一行「最近 N 天没有任务更新（最后更新 …）」。
    """
    raise NotImplementedError("TODO M2: 单人块")


# --------------------------------------------------------------------------
# LLM 要点 → 消息
# --------------------------------------------------------------------------

def strip_markdown(text: str) -> str:
    """去掉 `**` `__` 反引号 `#` `>` 列表符与代码围栏。"""
    raise NotImplementedError("TODO M2: 去 Markdown")


def split_points(points: list[str], max_chars: int = MAX_MSG) -> list[str]:
    """要点 → 可发送消息。丢空行、不加序号；超长按标点软切再硬切。"""
    raise NotImplementedError("TODO M2: 分条")
