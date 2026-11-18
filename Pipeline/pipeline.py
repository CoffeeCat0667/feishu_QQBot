"""一次运行的编排：拉数据 → 上下文 → 算风险 → LLM → 拼消息 → 发送。

只有这里同时接触 I/O 和纯逻辑；改数据源/换 LLM 只改这个文件。

失败语义（Q3/Q4）：
  - 前置（拉数据/渲染/算风险/LLM）失败 → 抛异常，**一条业务消息都不发**；
  - 发送阶段单条失败 → 重试后跳过，继续发下一条，最后汇总。
"""

from __future__ import annotations

import datetime as dt

from Feishu import feishu
from QQ import qq
from Report import report

INTERVAL_MS = 1500
SEND_RETRIES = 3


def build_messages(cfg: dict, now: dt.datetime) -> tuple[list[dict], dict]:
    """产出待发消息：标题+报告 + 按技术组的风险块。

    消息结构：
    1. 全局通报：标题 + LLM 进展报告
    2. 机械组：进度危险通报 + @ 人员
    3. 电控组：进度危险通报 + @ 人员
    4. 算法组：进度危险通报 + @ 人员
    ...
    
    消息格式：{"text": "消息文本"}；文本中的 \x00at:QQ号\x00 由 qq.send 转成 @ 段。
    """
    from Feishu import feishu
    from QQ import qq

    # 拉飞书数据
    tables = feishu.fetch(cfg)

    # 渲染上下文给 LLM
    context = report.render_context(tables)

    # 解析任务表
    tasks = report.parse_tasks(tables, "研发进展总表")

    # 风险分析（按技术组组织，检查所有表的更新时间）
    today = now.date()
    group_risks, stats = report.analyze(tables, tasks, today, now, near_days=cfg["risk"]["near_days"], idle_days=cfg["risk"]["idle_days"])
    low_members, low_units = report.analyze_workload(tasks, tables, now, cfg["risk"]["idle_days"])

    # 调用 LLM 生成进展报告（前置失败则整轮中止）
    report_text = ask_llm(cfg, context, stats)

    # 生成消息
    messages = []

    # 第 1 条消息：全局通报（标题 + LLM 进展报告）
    global_msg = report.title(now) + "\n\n" + report_text
    if low_units:
        global_msg += f"\n\n任务量提醒：{'、'.join(low_units)} 当前任务数明显偏少，请关注。"
    messages.append({"text": global_msg})

    # 第 2-N 条消息：按技术组分块，详细列出每个负责人的风险任务
    group_id = qq.resolve_group(cfg)
    for group_risk in group_risks:
        group_name = group_risk["group"]
        members = group_risk["members"]
        
        # 构建这个技术组的消息
        group_msg = f"{group_name}：进度危险通报\n\n"

        # 按负责人列出详细风险信息，姓名处嵌入内联 @ 标记
        for member in members:
            matched_qq = qq.match_qq(member["name"], group_id, cfg)
            name_part = f"\x00at:{matched_qq}\x00" if matched_qq else member["name"]
            group_msg += f"{name_part} 的进度风险：\n"
            
            # 列出超期任务
            for task in member["overdue"]:
                days_overdue = (today - task["due"]).days if task["due"] else 0
                progress_pct = int(task['progress']*100) if task['progress'] is not None else 0
                priority = task['priority'] or ""
                group_msg += f"{task['name']}（{task['status']}，预计 {task['due']}，已逾期 {days_overdue} 天，进度 {progress_pct}%，{priority}，{task['group']}）\n"
            
            # 列出临近任务
            for task in member["near"]:
                days_left = (task["due"] - today).days if task["due"] else 0
                progress_pct = int(task['progress']*100) if task['progress'] is not None else 0
                priority = task['priority'] or ""
                group_msg += f"{task['name']}（{task['status']}，预计 {task['due']}，还有 {days_left} 天，进度 {progress_pct}%，{priority}，{task['group']}）\n"

            # 列出无截止日且久未更新的任务（严重延期）
            for task in member.get("no_due_stale", []):
                days_stale = (now - task["updated"]).days if task.get("updated") else None
                stale_text = f"{days_stale} 天无进展" if days_stale is not None else "从未更新"
                progress_pct = int(task['progress']*100) if task['progress'] is not None else 0
                priority = task['priority'] or ""
                group_msg += f"{task['name']}（{task['status']}，无截止日，{stale_text}，进度 {progress_pct}%，{priority}，{task['group']}）\n"

            # 如果只有无更新风险
            if not member["overdue"] and not member["near"] and not member.get("no_due_stale") and member["idle_days"]:
                group_msg += f"最近 {member['idle_days']} 天没有任务更新\n"
            
            group_msg += "\n"

        # 任务量明显少于组内平均的负责人
        low_names = low_members.get(group_name, [])
        if low_names:
            parts = []
            for n in low_names:
                q = qq.match_qq(n, group_id, cfg)
                parts.append(f"\x00at:{q}\x00" if q else n)
            group_msg += f"任务量提醒：{'、'.join(parts)} 当前任务数明显少于组内平均，请关注。\n"

        messages.append({"text": group_msg.strip()})

    # 对有人员偏少但无风险成员的职能组，单独发一条提醒
    groups_with_msg = {g["group"] for g in group_risks}
    for group_name, low_names in low_members.items():
        if group_name in groups_with_msg:
            continue  # 已追加到该组的危险通报里
        parts = []
        for n in low_names:
            q = qq.match_qq(n, group_id, cfg)
            parts.append(f"\x00at:{q}\x00" if q else n)
        msg = f"{group_name}：数据提醒\n\n任务量提醒：{'、'.join(parts)} 当前任务数明显少于组内平均，请关注。"
        messages.append({"text": msg})

    # 统计
    result_stats = {
        "tables": len(tables),
        "rows": sum(len(t.get("records", [])) for t in tables.values()),
        "chars": sum(len(str(v)) for t in tables.values() for r in t.get("records", []) for v in r.values()),
        "points": 1,  # LLM 生成的进展报告算一个
        "tasks": len(tasks),
        "overdue": stats["overdue"],
        "near": stats["near"],
    }

    return messages, result_stats


def ask_llm(cfg: dict, context: str, stats: dict) -> str:
    """调用 OpenAI 兼容 API，返回一段连续的进展报告文字。
    
    失败时抛 RuntimeError，由上层捕获并上报。
    """
    import requests
    
    api_key = cfg["llm"]["api_key"]
    base_url = cfg["llm"]["base_url"].rstrip("/")
    model = cfg["llm"]["model"]
    
    # 构建 prompt
    persona = cfg.get("prompt", {}).get("persona", "进度报告专家")
    style = cfg.get("prompt", {}).get("style", "精准简洁")
    output_format = cfg.get("prompt", {}).get("output_format", "段落文字")
    task_hint = cfg.get("prompt", {}).get("task_hint", "")
    
    # 截断过长的上下文
    max_context = 5000
    if len(context) > max_context:
        context = context[:max_context] + "\n（上下文已截断）"
    
    prompt = (
        f"角色：{persona}\n"
        f"风格：{style}\n"
        f"格式：{output_format}\n\n"
        f"任务提示：{task_hint}\n\n"
        f"表格概览：\n{context}\n\n"
        f"统计数据：\n"
        f"- 总任务数：{stats.get('total', 0)}\n"
        f"- 已完成：{stats.get('done', 0)}\n"
        f"- 逾期：{stats.get('overdue', 0)}\n"
        f"- 临近截止：{stats.get('near', 0)}\n\n"
        f"请生成一段连续的进展报告文字（200-300字），总结当前项目进度、完成情况和存在的风险。"
        f"报告中的数字必须来自上述统计数据。"
    )
    
    # 调用 OpenAI API
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": cfg["llm"].get("temperature", 0.7),
            "max_tokens": cfg["llm"].get("max_tokens", 500),
        }
        
        resp = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        
        if "error" in data:
            raise RuntimeError(f"LLM 返回错误：{data['error']}")
        
        message = data["choices"][0]["message"]["content"].strip()
        
        if not message:
            raise RuntimeError("LLM 返回空内容")
        
        return message
        
    except requests.RequestException as exc:
        raise RuntimeError(f"LLM API 调用失败：{exc}") from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise RuntimeError(f"LLM 返回格式错误：{exc}") from exc


def send_all(cfg: dict, messages: list[dict]) -> tuple[int, int]:
    """逐条发送，间隔 1.5s；单条失败重试 3 次后跳过。返回 (成功, 失败)。"""
    import time
    import logging
    
    LOG = logging.getLogger("qqbot")
    group_id = qq.resolve_group(cfg)
    sent = 0
    failed = 0
    
    for i, msg in enumerate(messages):
        text = msg["text"]
        for attempt in range(1, SEND_RETRIES + 1):
            try:
                qq.send(cfg, str(group_id), text)
                sent += 1
                break
            except Exception as exc:
                if attempt == SEND_RETRIES:
                    LOG.error(f"消息 {i+1} 失败（{attempt} 次重试后）: {exc}")
                    failed += 1
                else:
                    LOG.warning(f"消息 {i+1} 失败（第 {attempt} 次，将重试）: {exc}")
                    time.sleep(1)
        
        if i < len(messages) - 1:
            time.sleep(INTERVAL_MS / 1000.0)
    
    return sent, failed
