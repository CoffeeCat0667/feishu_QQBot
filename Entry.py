"""入口：CLI、主循环、触发判定、state.json、管理员日志。

    python Entry.py --check       # 体检：校时 / 飞书 / NapCat / 群与成员
    python Entry.py --once        # 立即跑一次（真实发送）
    python Entry.py               # 常驻：首启跑一次，之后按 times 触发

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

from Clock import clock as clock_mod
from Config import config as config_mod
from Pipeline import pipeline
from QQ import qq
from Report import report

POLL_SECONDS = 5
TOLERANCE_SECONDS = 30
RETRY_AFTER_ERROR = 30

LOG = logging.getLogger("qqbot")


# --------------------------------------------------------------------------
# state.json —— 只回答一个问题：今天这个时间点跑过没有
# --------------------------------------------------------------------------

def read_state(path: str | Path) -> dict:
    """读不到/损坏 → `{"fired": {}, "last_run_at": ""}` + WARNING。"""
    empty = {"fired": {}, "last_run_at": ""}
    try:
        with Path(path).open(encoding="utf-8") as f:
            state = json.load(f)
        if not isinstance(state, dict):
            raise ValueError("state 顶层不是对象")
        fired = state.get("fired", {})
        last_run_at = state.get("last_run_at", "")
        if not isinstance(fired, dict) or not isinstance(last_run_at, str):
            raise ValueError("state 字段格式无效")
        if any(
            not isinstance(day, str)
            or not isinstance(slots, list)
            or any(not isinstance(slot, str) for slot in slots)
            for day, slots in fired.items()
        ):
            raise ValueError("state.fired 格式无效")
        return {"fired": fired, "last_run_at": last_run_at}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        LOG.warning("读取状态失败，按空状态继续: %s", exc)
        return empty


def write_state(path: str | Path, state: dict) -> None:
    """先写 `.tmp` 再 `os.replace`，断电不会留下半个 JSON。"""
    path = Path(path)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def due_slot(times: list[str], now: dt.datetime, state: dict) -> str | None:
    """命中则返回该时间点标签（如 "09:00"），否则 None。

    使用日内环形距离，去重键是 (触发日期, 标签)。
    """
    now_seconds = now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1_000_000
    fired = state.get("fired", {})

    for label in times:
        parts = label.split(":")
        if len(parts) not in (2, 3):
            continue
        try:
            hour, minute = int(parts[0]), int(parts[1])
            second = int(parts[2]) if len(parts) == 3 else 0
        except ValueError:
            continue
        if hour > 23 or minute > 59 or second > 59:
            continue

        slot_seconds = hour * 3600 + minute * 60 + second
        distance = abs(now_seconds - slot_seconds)
        distance = min(distance, 86400 - distance)
        slot_day = now.date()
        if slot_seconds - now_seconds > 43200:
            slot_day -= dt.timedelta(days=1)
        elif now_seconds - slot_seconds > 43200:
            slot_day += dt.timedelta(days=1)
        fired_slots = fired.get(slot_day.isoformat(), []) if isinstance(fired, dict) else []
        if distance <= TOLERANCE_SECONDS and label not in fired_slots:
            return label
    return None


# --------------------------------------------------------------------------
# 日志与管理员
# --------------------------------------------------------------------------

def setup_logging(level: str = "INFO") -> None:
    """stderr 输出，格式 `HH:MM:SS LEVEL message`。"""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"))
    logging.basicConfig(level=getattr(logging, level, "INFO"), handlers=[handler])


def summarize(result: dict, elapsed: float) -> str:
    """一次运行的汇总文本（5 行，就这 5 行，别加第 6 行）。"""
    return (
        f"【进展通报】\n"
        f"表: {result['tables']} | 行: {result['rows']} | 字: {result['chars']}\n"
        f"消息: {result['points']} | 已发: {result['sent']} | 失败: {result['failed']}\n"
        f"用时: {elapsed:.1f}s\n"
        f"✓"
    )


# --------------------------------------------------------------------------
# 子命令
# --------------------------------------------------------------------------

def cmd_check(cfg: dict) -> int:
    """体检：校时、飞书、NapCat、目标群、成员匹配。"""
    from Feishu import feishu
    from QQ import qq

    try:
        # 校时
        print("[校时]", end=" ")
        clk = clock_mod.Clock(tuple(cfg["ntp_servers"]))
        source = clk.sync()
        now = clk.now()
        print(f"{source}  UTC+8={now.strftime('%Y-%m-%d %H:%M:%S')}")

        # 飞书
        print("[飞书]", end=" ")
        tables = feishu.fetch(cfg)
        total_rows = sum(len(t.get("records", [])) for t in tables.values())
        total_chars = sum(
            sum(len(str(v)) for v in r.values())
            for t in tables.values()
            for r in t.get("records", [])
        )
        print(f"{len(tables)} 张表 / {total_rows} 行 / {total_chars:,} 字")

        # NapCat
        print("[NapCat]", end=" ")
        login = qq.login_info(cfg)
        user_id = login.get("user_id", "?")
        nickname = login.get("nickname", "?")
        print(f"{user_id} {nickname}")

        # 目标群
        print("[目标]", end=" ")
        group_id = qq.resolve_group(cfg)
        target_name = cfg["target"]["group"]
        print(f"{target_name} -> {group_id}")

        # 成员匹配
        print("[成员匹配]", end=" ")
        member_list = qq.members(cfg, group_id)
        owner_names = set()
        for table in tables.values():
            for record in table.get("records", []):
                owner = record.get("任务负责人", "")
                if owner:
                    owner_names.add(owner)

        matched = 0
        for owner in owner_names:
            if qq.match_qq(owner, group_id, cfg) is not None:
                matched += 1

        print(f"{len(member_list)} 人；负责人 {len(owner_names)} 个中匹配到 {matched} 个")
        return 0

    except Exception as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1


def run_and_report(cfg: dict, clk: clock_mod.Clock) -> bool:
    """跑一轮 + 汇总上报。前置失败时整轮中止且上报错误，不发送业务消息。"""
    import time
    from QQ import qq

    start = time.time()
    admin_id = cfg.get("admin", 0)

    try:
        # 前置阶段（拉数据、LLM、风险分析）- 任何失败都中止
        messages, stats = pipeline.build_messages(cfg, clk.now())

        # 发送阶段 - 单条失败重试后跳过
        sent, failed = pipeline.send_all(cfg, messages)

        elapsed = time.time() - start
        result = {
            "tables": stats.get("tables", 0),
            "rows": stats.get("rows", 0),
            "chars": stats.get("chars", 0),
            "points": stats.get("points", 0),
            "sent": sent,
            "failed": failed,
            "unmatched": [],
        }

        # 成功汇总上报给管理员
        summary = summarize(result, elapsed)
        try:
            if admin_id:
                qq.send(cfg, f"private:{admin_id}", summary)
        except Exception as exc:
            LOG.error("管理员上报失败: %s", exc)

        return failed == 0

    except Exception as exc:
        elapsed = time.time() - start
        LOG.exception("前置阶段失败，整轮中止")

        # 前置失败 - 向管理员发送错误报告，不发送业务消息
        try:
            if admin_id:
                error_msg = f"【错误】前置阶段失败\n错误：{str(exc)}\n用时：{elapsed:.1f}s"
                qq.send(cfg, f"private:{admin_id}", error_msg)
        except Exception as exc2:
            LOG.exception("错误上报失败: %s", exc2)

        return False


def service(cfg: dict) -> int:
    """常驻主循环。首启立即跑一次（D9），之后每 5 秒看一次表。"""
    clk = clock_mod.Clock(tuple(cfg["ntp_servers"]))
    while True:
        try:
            clk.sync()
            break
        except Exception:
            LOG.exception("NTP 校时失败，%s 秒后重试", RETRY_AFTER_ERROR)
            time.sleep(RETRY_AFTER_ERROR)

    state_path = cfg["state_path"]
    state = read_state(state_path)

    def mark_fired(slot: str | None, now: dt.datetime) -> None:
        now_seconds = now.hour * 3600 + now.minute * 60 + now.second
        if slot is not None:
            parts = slot.split(":")
            slot_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60
            if len(parts) == 3:
                slot_seconds += int(parts[2])
            slot_day = now.date()
            if slot_seconds - now_seconds > 43200:
                slot_day -= dt.timedelta(days=1)
            elif now_seconds - slot_seconds > 43200:
                slot_day += dt.timedelta(days=1)

            slots = state["fired"].setdefault(slot_day.isoformat(), [])
            if slot not in slots:
                slots.append(slot)
        state["last_run_at"] = now.isoformat()
        write_state(state_path, state)

    now = clk.now()
    startup_slot = due_slot(cfg["times"], now, state)
    mark_fired(startup_slot, now)
    try:
        run_and_report(cfg, clk)
    except Exception:
        LOG.exception("启动运行失败")

    while True:
        try:
            now = clk.now()
            slot = due_slot(cfg["times"], now, state)
            if slot:
                mark_fired(slot, now)
                run_and_report(cfg, clk)
        except Exception:
            LOG.exception("定时运行失败")
            time.sleep(RETRY_AFTER_ERROR)
            continue
        time.sleep(POLL_SECONDS)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="Entry.py", description="QQ 定时进展通报机器人")
    p.add_argument("--config")
    p.add_argument("--check", action="store_true", help="体检")
    p.add_argument("--once", action="store_true", help="立即跑一次（真实发送）")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    default_config = Path(__file__).resolve().parent / "Config" / "config.json"
    config_path = os.environ.get("QQBOT_CONFIG", args.config or default_config)
    cfg = config_mod.load(config_path)
    setup_logging()

    if args.check:
        return cmd_check(cfg)
    if args.once:
        clk = clock_mod.Clock(tuple(cfg["ntp_servers"]))
        clk.sync()
        return 0 if run_and_report(cfg, clk) else 1
    return service(cfg)


if __name__ == "__main__":
    sys.exit(main())
