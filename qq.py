"""NapCat / OneBot v11：发消息、名称解析与群成员匹配。

协议：`POST {api}/{action}`，JSON body 即参数，头 `Authorization: Bearer {token}`。
消息用 array 段格式：

    [{"type": "at", "data": {"qq": "123"}},
     {"type": "text", "data": {"text": " 的进度风险：..."}}]

实测坑（PLAN §11）：
  - `get_group_list` 不完整（2 个群只返回 1 个）→ 必须用 `get_recent_contact` 兜底；
  - token 为空时 NapCat 不校验来源 —— 不要留空。
"""

from __future__ import annotations

import requests

TIMEOUT = 15


# --------------------------------------------------------------------------
# OneBot
# --------------------------------------------------------------------------

def api(cfg: dict, action: str, params: dict | None = None) -> dict:
    """调一个 OneBot action，返回 `data`。retcode != 0 抛 RuntimeError。"""
    raise NotImplementedError("TODO M3: OneBot 调用")


def login_info(cfg: dict) -> dict:
    """`get_login_info` → {"user_id", "nickname"}。"""
    raise NotImplementedError("TODO M3: 登录信息")


def resolve_group(cfg: dict) -> int:
    """`target.group` → 群号。

    降级链：纯数字 → `get_group_list` 按群名精确匹配 → `get_recent_contact` 兜底。
    """
    raise NotImplementedError("TODO M3: 群号解析")


def resolve_friend(cfg: dict, name: str) -> int:
    """好友昵称/备注 → QQ 号（`get_friend_list` → `get_recent_contact`）。"""
    raise NotImplementedError("TODO M3: 好友解析")


def members(cfg: dict, group_id: int) -> list[dict]:
    """`get_group_member_list` → [{"user_id", "nickname", "card"}]。"""
    raise NotImplementedError("TODO M3: 群成员")


def match_qq(name: str, group_id: int, cfg: dict) -> int | None:
    """姓名 → QQ（PLAN §5.5 匹配链，命中即返回）：

        1. risk.aliases[name]       手工覆盖，最高优先级
        2. 群名片 card == name
        3. 昵称 nickname == name
        4. card/nickname 包含 name  仅唯一命中采用，多命中视为失败
        5. None → 块照发，只写姓名，不标注「未匹配」（D22）
    """
    raise NotImplementedError("TODO M3: 姓名匹配")


def send(cfg: dict, target: str, text: str, at: int | None = None) -> int:
    """`target` 是群号或 "private:<qq>"。返回 message_id。"""
    raise NotImplementedError("TODO M3: 发送")
