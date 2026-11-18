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

DONE = ["完成", "已完成"]  # 飞书中的所有完成状态值
MAX_CELL = 300                 # 单元格截断长度
MAX_TOTAL = 120000             # 上下文总长上限，超了从后往前丢表
MAX_MSG = 800                  # 单条消息字数上限

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "": 9}
TASK_FIELDS = (
    "任务ID", "任务名称", "任务负责人", "任务状态", "优先级",
    "预计完成日", "进度百分比", "职能组", "今日进展", "最后更新时间",
)

# 兵种权重（仅用于内部计算，不输出到消息）
_UNIT_WEIGHT: dict[str, int] = {
    "重装": 16,
    "步兵": 11,
    "哨兵": 6,
    "无人机": 4,
    "飞镖组": 2,
    "雷达": 1,
    "场地道具": 1,
}
# 周进度规划表里的兵种写法 → 权重表里的名字
_UNIT_ALIAS = {"飞镖": "飞镖组", "空中": "无人机"}


# --------------------------------------------------------------------------
# 表格 → 上下文
# --------------------------------------------------------------------------

def render_context(tables: dict[str, dict]) -> str:
    """全部表 → 一段 Markdown。去掉任务 ID。超长时从最后一张表开始丢并注明。"""
    lines = []
    total = 0

    for table_id, table_data in tables.items():
        table_name = table_data.get("name", table_id)
        records = table_data.get("records", [])
        
        if not records:
            continue
        
        # 表标题
        table_text = f"## {table_name}\n\n"
        
        # 记录行（跳过任务 ID 字段）
        for record in records:
            cells = []
            for key, val in record.items():
                # 跳过任务 ID 和其他不必要字段
                if "ID" in key or "id" in key.lower():
                    continue
                cells.append(format_cell(str(val)))
            
            if cells:  # 只有非空字段才添加
                table_text += "| " + " | ".join(cells) + " |\n"
        
        table_text += "\n"
        
        if total + len(table_text) <= MAX_TOTAL:
            lines.append(table_text)
            total += len(table_text)
        else:
            # 超长时跳过这张表
            lines.append(f"\n（剩余表格超长已省略）\n")
            break
    
    return "".join(lines)


def format_cell(value: str, max_chars: int = MAX_CELL) -> str:
    """单元格扁平化：`|` → `/`、换行 → 空格、超长截断加 `…`。"""
    value = str(value).replace("|", "/").replace("\n", " ").strip()
    if len(value) > max_chars:
        value = value[:max_chars-1] + "…"
    return value


# --------------------------------------------------------------------------
# 记录 → 任务
# --------------------------------------------------------------------------

def ts(value) -> dt.datetime | None:
    """毫秒时间戳 → UTC+8 datetime；空/非法返回 None。"""
    if not value or value == "":
        return None
    try:
        timestamp = float(value)
        if timestamp <= 0:
            return None
        if timestamp > 1e11:
            timestamp = timestamp / 1000.0
        from Clock import clock
        return dt.datetime.fromtimestamp(timestamp, tz=clock.UTC8)
    except (TypeError, ValueError, OverflowError):
        return None


def progress(value) -> float | None:
    """`"0.21"` → 0.21；空/非法 → None。实测是 0~1 的**字符串**。"""
    if not value or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def owner_name(value) -> str:
    """人员字段 → 姓名。list 取每项 name，dict 取 name，str 原样 strip。
    
    绝不按空格切：`算法 顾子奕 小登` 是一个人的注册名。
    """
    if not value:
        return ""
    if isinstance(value, list):
        names = []
        for item in value:
            if isinstance(item, dict):
                names.append(item.get("name", ""))
            else:
                names.append(str(item))
        return "、".join(n for n in names if n)
    elif isinstance(value, dict):
        return value.get("name", "")
    else:
        return str(value).strip()


def parse_tasks(tables: dict[str, dict], task_table_name: str = "研发进展总表") -> list[dict]:
    """取出任务表 → 归一化 dict 列表。

    截止日期支持：时间戳（毫秒）或 ISO 格式字符串。
    
        {"id", "name", "owner", "status", "priority", "group",
         "due": date|None, "progress": float|None, "updated": datetime|None}
    """
    tasks = []
    
    # 找任务表
    task_table = None
    for table_id, table_data in tables.items():
        if table_data.get("name") == task_table_name or table_id == task_table_name:
            task_table = table_data
            break
    
    if not task_table:
        return tasks
    
    for record in task_table.get("records", []):
        status = record.get("任务状态", "")
        task = {
            "id": record.get("任务ID", ""),
            "name": record.get("任务名称", ""),
            "owner": owner_name(record.get("任务负责人", "")),
            "status": status,
            "priority": record.get("优先级", ""),
            "group": record.get("职能组", ""),
            "unit": record.get("所属兵种", ""),
            "due": None,
            "progress": progress(record.get("进度百分比")),
            "updated": ts(record.get("最后更新时间")),
        }
        
        # 解析预计完成日（支持时间戳毫秒和ISO字符串）
        due_val = record.get("预计完成日", "")
        if due_val:
            try:
                # 尝试作为时间戳（毫秒）
                if isinstance(due_val, (int, float)):
                    task["due"] = dt.datetime.fromtimestamp(due_val/1000, tz=dt.timezone.utc).date()
                # 尝试作为ISO字符串
                elif isinstance(due_val, str) and due_val.strip():
                    task["due"] = dt.datetime.fromisoformat(due_val.strip()).date()
            except (ValueError, TypeError, OSError):
                task["due"] = None
        
        if task["name"]:  # 只加有任务名的
            tasks.append(task)
    
    return tasks


# --------------------------------------------------------------------------
# 任务量偏少
# --------------------------------------------------------------------------


def analyze_workload(
    tasks: list[dict],
    tables: dict[str, dict],
    now: dt.datetime,
    idle_days: int = 15,
) -> tuple[dict[str, list[str]], list[str]]:
    """兵种任务量偏少 & 人员条目偏少且不活跃。

    兵种：在所有非研发进展总表的表中按所属兵种统计总条目数（含已完成），
          score = count / weight，score 低于组均值 60% 的兵种标记偏少。

    人员：在全量表（所有表）中统计每人出现在负责人/参与成员字段的总条目数，
          从主表确定人员所属职能组（机械/电控/算法），
          同时满足"条目数 < 组均值 60%"且"最后更新距今 > idle_days 天"才标记偏少。

    返回 ({组名: [负责人]}, [兵种])。需在 analyze() 之后调用（它会把进度 100% 的任务标为完成）。
    """
    TASK_TABLE = "研发进展总表"

    # ---- 兵种：非主表中按所属兵种统计总条目数 ----
    unit_count: dict[str, int] = {u: 0 for u in _UNIT_WEIGHT}
    for td in tables.values():
        if td.get("name") == TASK_TABLE:
            continue
        for r in td.get("records", []):
            u = str(r.get("所属兵种", "") or "").strip()
            u = _UNIT_ALIAS.get(u, u)
            if u in unit_count:
                unit_count[u] += 1

    scores = {u: c / _UNIT_WEIGHT[u] for u, c in unit_count.items() if c > 0}
    if scores:
        mean_score = sum(scores.values()) / len(scores)
        threshold_unit = mean_score * 0.6
    else:
        threshold_unit = 0
    # 周进度表里没有条目的兵种不参与比较，也不提醒
    low_units = sorted(
        u for u, s in scores.items() if s < threshold_unit
    )

    # ---- 人员：全量表统计条目数和最后活跃时间 ----
    person_count: dict[str, int] = {}
    person_last: dict[str, dt.datetime] = {}
    for td in tables.values():
        for r in td.get("records", []):
            names: set[str] = set()
            for field in ("负责人", "参与成员", "任务负责人"):
                v = r.get(field)
                if v:
                    for part in owner_name(v).split("、"):
                        p = part.strip()
                        if p:
                            names.add(p)
            upd = ts(r.get("最后更新时间"))
            for name in names:
                person_count[name] = person_count.get(name, 0) + 1
                if upd and (name not in person_last or upd > person_last[name]):
                    person_last[name] = upd

    # 从主表确定人员→职能组（取出现最多次的职能组）
    group_votes: dict[str, dict[str, int]] = {}
    task_table = next((td for td in tables.values() if td.get("name") == TASK_TABLE), {})
    for r in task_table.get("records", []):
        o = owner_name(r.get("任务负责人", ""))
        g = str(r.get("职能组", "") or "").strip()
        if o and g:
            group_votes.setdefault(o, {})
            group_votes[o][g] = group_votes[o].get(g, 0) + 1
    person_group = {o: max(gv, key=gv.get) for o, gv in group_votes.items()}

    # 按职能组分组，找"条目偏少 AND 不活跃"的人
    group_people: dict[str, list[str]] = {}
    for person, group in person_group.items():
        group_people.setdefault(group, []).append(person)

    low_members: dict[str, list[str]] = {}
    for group, people in group_people.items():
        counts = {p: person_count.get(p, 0) for p in people}
        avg = sum(counts.values()) / len(counts) if counts else 0
        threshold_person = avg * 0.6
        low = []
        for p, c in counts.items():
            if c >= threshold_person:
                continue
            last = person_last.get(p)
            days_idle = (now - last).days if last else None
            if days_idle is None or days_idle > idle_days:
                low.append(p)
        if low:
            low_members[group] = sorted(low)

    return low_members, low_units


# --------------------------------------------------------------------------
# 任务 → 风险
# --------------------------------------------------------------------------

def analyze(
    tables: dict[str, dict],
    tasks: list[dict],
    today: dt.date,
    now: dt.datetime,
    near_days: int = 5,
    idle_days: int = 15,
) -> tuple[list[dict], dict]:
    """风险分析 → 按技术组组织风险人员（含详细危险原因）。

    风险类型：
    1. 超期：预计完成日 < 今天且未完成
    2. 临近：预计完成日 <= 5天且未完成
    3. 无更新：表内15天内无任何任务或更新
    
    返回 (技术组风险列表, 总统计)
    
    技术组风险格式：
        {"group": "机械组", "members": [
            {
                "name": "张三",
                "overdue": [任务],
                "near": [任务],
                "idle_days": 20,
                "reasons": ["超期", "无更新"]
            }
        ]}
    """
    # 进度 100% 但未标已完成 → 按已完成处理
    for task in tasks:
        if task["progress"] == 1.0 and task["status"] not in DONE:
            task["status"] = DONE[0]
    
    stats = {"total": 0, "done": 0, "blocked": 0, "overdue": 0, "near": 0}
    by_group: dict[str, dict] = {}
    
    # 第一步：遍历主表任务，只收集未完成的风险信息
    for task in tasks:
        stats["total"] += 1
        
        # 判定完成（早期过滤）
        if task["status"] in DONE:
            stats["done"] += 1
            continue
        
        group = task["group"] or "未分类"
        owner = task["owner"] or "未指定"
        
        if group not in by_group:
            by_group[group] = {"group": group, "members": {}}
        
        if owner not in by_group[group]["members"]:
            by_group[group]["members"][owner] = {
                "name": owner,
                "overdue": [],
                "near": [],
                "no_due_stale": [],
                "idle_days": None,
                "last_update": None,
            }
        
        # 更新最后修改时间（主表）
        if task["updated"]:
            member_data = by_group[group]["members"][owner]
            if member_data["last_update"] is None or task["updated"] > member_data["last_update"]:
                member_data["last_update"] = task["updated"]
        
        # 判定超期
        if task["due"] and task["due"] < today:
            by_group[group]["members"][owner]["overdue"].append(task)
            stats["overdue"] += 1
        # 判定临近
        elif task["due"]:
            days_left = (task["due"] - today).days
            if 0 <= days_left <= near_days:
                by_group[group]["members"][owner]["near"].append(task)
                stats["near"] += 1
        # 无截止日且 30 天内无更新 → 严重延期
        elif task["due"] is None:
            stale_days = (now - task["updated"]).days if task["updated"] else None
            if stale_days is None or stale_days > 30:
                by_group[group]["members"][owner]["no_due_stale"].append(task)
                stats["overdue"] += 1
    
    # 第二步：遍历所有表，收集每个人在所有表中的最新更新时间
    # 构建所有出现过的人员列表（从所有表中）
    all_people: dict[str, dt.datetime | None] = {}
    
    for table_id, table_data in tables.items():
        records = table_data.get("records", [])
        for record in records:
            person_name_str = owner_name(record.get("任务负责人", ""))
            if not person_name_str or person_name_str == "未指定":
                continue
            
            updated = ts(record.get("最后更新时间", ""))
            if updated:
                if person_name_str not in all_people or all_people[person_name_str] is None:
                    all_people[person_name_str] = updated
                elif updated > all_people[person_name_str]:
                    all_people[person_name_str] = updated
    
    # 更新 by_group 中每个人的最后更新时间（取所有表中的最新）
    owner_to_group: dict[str, str] = {}
    for group_name, group_data in by_group.items():
        for member_name in group_data["members"]:
            owner_to_group[member_name] = group_name
    
    for person_name, latest_update in all_people.items():
        if person_name in owner_to_group:
            group = owner_to_group[person_name]
            member_data = by_group[group]["members"][person_name]
            if member_data["last_update"] is None or latest_update > member_data["last_update"]:
                member_data["last_update"] = latest_update
    
    # 第三步：构建返回结果，列出所有危险原因
    result = []
    for group_name, group_data in by_group.items():
        risk_members = []
        
        for member_name, member_data in group_data["members"].items():
            # 收集所有危险原因
            reasons = []
            
            if member_data["overdue"]:
                reasons.append("超期")
            if member_data["near"]:
                reasons.append("临近")
            if member_data["no_due_stale"]:
                reasons.append("严重延期")
            
            # 检查无更新（15天内无任何记录）
            idle_days_count = None
            if member_data["last_update"]:
                days_idle = (now - member_data["last_update"]).days
                if days_idle > idle_days:
                    reasons.append("无更新")
                    idle_days_count = days_idle
            elif not member_data["overdue"] and not member_data["near"]:
                # 没有更新时间记录，说明是新人或无记录
                reasons.append("无更新")
            
            if reasons:
                risk_members.append({
                    "name": member_name,
                    "overdue": member_data["overdue"],
                    "near": member_data["near"],
                    "no_due_stale": member_data["no_due_stale"],
                    "idle_days": idle_days_count,
                    "reasons": reasons,
                })
        
        if risk_members:
            result.append({
                "group": group_name,
                "members": risk_members,
            })
    
    # 按最早截止日排序
    for group in result:
        group["members"].sort(key=lambda m: min(
            [t["due"] for t in m["overdue"] + m["near"] if t["due"]], 
            default=dt.date.max
        ))
    
    return result, stats


# --------------------------------------------------------------------------
# 风险 → 消息文本
# --------------------------------------------------------------------------

def title(now: dt.datetime) -> str:
    """`11 月 17 日 进展通报`"""
    month = now.month
    day = now.day
    return f"{month} 月 {day} 日 进展通报"


def render_block(row: dict, today: dt.date) -> list[str]:
    """一个人的块 → 行列表（第一行不含 @，@ 由 qq.py 拼）。

        ["的进度风险：",
         "底盘拼装（阻塞，预计 2026-09-08，已逾期 70 天，进度 21%，P1，机械）",
         ...]

    TODO M3：括号内固定 状态 → 预计完成日 → 逾期/剩余天数 → 进度 → 优先级 → 职能组。
    """
    lines = ["的进度风险："]
    
    overdue = row.get("overdue", [])
    near = row.get("near", [])
    idle_days = row.get("idle_days")
    
    # 如果没有超期/临近，只输出久未更新
    if not overdue and not near and idle_days:
        lines.append(f"最近 {idle_days} 天没有任务更新")
        return lines
    
    # 输出超期任务
    for task in overdue:
        days_overdue = (today - task["due"]).days if task["due"] else 0
        parts = []
        if task["status"] and task["status"] not in DONE:
            parts.append(task["status"])
        if task["due"]:
            parts.append(f"预计 {task['due']}")
        if days_overdue > 0:
            parts.append(f"已逾期 {days_overdue} 天")
        if task["progress"] is not None:
            parts.append(f"进度 {task['progress']*100:.0f}%")
        if task["priority"]:
            parts.append(task["priority"])
        if task["group"]:
            parts.append(task["group"])
        
        line = f"{task['name']}（{', '.join(parts)}）" if parts else task["name"]
        lines.append(line)
    
    # 输出临近任务
    for task in near:
        days_left = (task["due"] - today).days if task["due"] else 0
        parts = []
        if task["status"] and task["status"] not in DONE:
            parts.append(task["status"])
        if task["due"]:
            parts.append(f"预计 {task['due']}")
        if days_left >= 0:
            parts.append(f"还有 {days_left} 天")
        if task["progress"] is not None:
            parts.append(f"进度 {task['progress']*100:.0f}%")
        if task["priority"]:
            parts.append(task["priority"])
        if task["group"]:
            parts.append(task["group"])
        
        line = f"{task['name']}（{', '.join(parts)}）" if parts else task["name"]
        lines.append(line)
    
    return lines


def strip_markdown(text: str) -> str:
    """去掉 `**` `__` 反引号 `#` `>` 列表符与代码围栏。"""
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return text


def split_points(points: list[str], max_chars: int = MAX_MSG) -> list[str]:
    """要点 → 可发送消息。丢空行、不加序号；超长按标点软切再硬切。"""
    messages = []
    current = ""
    
    for point in points:
        point = point.strip()
        if not point:
            continue
        
        if len(current) + len(point) + 1 <= max_chars:
            current += (point + "\n") if current else point
        else:
            if current:
                messages.append(current)
            current = point
    
    if current:
        messages.append(current)
    
    return messages
