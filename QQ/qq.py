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

# 群成员缓存：{group_id: (成员列表, 拉取时的 monotonic 时间)}，避免同一次运行重复拉取
_member_cache: dict[int, tuple] = {}
_MEMBER_CACHE_TTL = 60  # 秒


# --------------------------------------------------------------------------
# OneBot
# --------------------------------------------------------------------------

def api(cfg: dict, action: str, params: dict | None = None) -> dict:
    """调一个 OneBot action，返回 `data`。retcode != 0 抛 RuntimeError。"""
    import json
    
    url = f"{cfg['napcat']['api']}/{action}"
    headers = {
        "Authorization": f"Bearer {cfg['napcat']['token']}",
        "Content-Type": "application/json; charset=utf-8",
    }
    try:
        resp = requests.post(url, json=params or {}, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        # 直接从原始字节用 UTF-8 解码和解析 JSON，避免 requests 的自动编码检测
        text = resp.content.decode('utf-8')
        body = json.loads(text)
    except requests.RequestException as exc:
        raise RuntimeError(f"OneBot API 失败 ({action}): {exc}") from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"OneBot 返回非 JSON ({action}): {exc}") from exc

    retcode = body.get("retcode")
    if retcode != 0:
        msg = body.get("msg", "未知错误")
        raise RuntimeError(f"OneBot 错误 ({action}): retcode={retcode}, msg={msg}")

    return body.get("data", {})



def login_info(cfg: dict) -> dict:
    """`get_login_info` → {"user_id", "nickname"}。"""
    return api(cfg, "get_login_info")


def resolve_group(cfg: dict) -> int:
    """`target.group` → 群号。

    降级链：纯数字 → `get_group_list` 按群名精确匹配 → `get_recent_contact` 兜底。
    """
    target = cfg["target"]["group"]
    
    # 尝试直接解析为数字
    try:
        return int(target)
    except ValueError:
        pass
    
    # 从 get_group_list 按名字查找
    groups = api(cfg, "get_group_list")
    if isinstance(groups, list):
        for group in groups:
            if group.get("group_name") == target:
                return int(group["group_id"])
    
    # 从 get_recent_contact 兜底
    contacts = api(cfg, "get_recent_contact")
    if isinstance(contacts, list):
        for contact in contacts:
            if contact.get("group_id") and contact.get("group_name") == target:
                return int(contact["group_id"])
    
    raise RuntimeError(f"无法解析目标群：{target}")


def resolve_friend(cfg: dict, name: str) -> int:
    """好友昵称/备注 → QQ 号（`get_friend_list` → `get_recent_contact`）。"""
    friends = api(cfg, "get_friend_list")
    if isinstance(friends, list):
        for friend in friends:
            if friend.get("nickname") == name or friend.get("remark") == name:
                return int(friend["user_id"])
    
    # 从 get_recent_contact 兜底
    contacts = api(cfg, "get_recent_contact")
    if isinstance(contacts, list):
        for contact in contacts:
            if not contact.get("group_id") and (contact.get("nickname") == name or contact.get("remark") == name):
                return int(contact["user_id"])
    
    raise RuntimeError(f"无法解析好友：{name}")


def members(cfg: dict, group_id: int) -> list[dict]:
    """`get_group_member_list` → [{"user_id", "nickname", "card"}]。

    结果在进程内缓存 60 秒，避免同一次运行里对同一群重复拉取。
    """
    import time as _time
    cached = _member_cache.get(group_id)
    if cached:
        result, ts = cached
        if _time.monotonic() - ts < _MEMBER_CACHE_TTL:
            return result

    result = api(cfg, "get_group_member_list", {"group_id": group_id})
    if isinstance(result, dict):
        result = result.get("members", [])
    if not isinstance(result, list):
        return []

    # 实测坑：get_group_member_list 的 card 为空或是旧缓存，必须逐人用 get_group_member_info(no_cache) 覆盖
    for m in result:
        info = api(cfg, "get_group_member_info", {"group_id": group_id, "user_id": m["user_id"], "no_cache": True})
        m["card"] = info.get("card") or ""
    _member_cache[group_id] = (result, _time.monotonic())
    return result


def match_qq(name: str, group_id: int, cfg: dict) -> int | None:
    """姓名 → QQ（PLAN §5.5 匹配链，命中即返回）：

        1. risk.aliases[name]                手工覆盖，最高优先级
        2. 群名片 card == name
        3. 昵称 nickname == name
        4. card/nickname 模糊匹配（如"李许多-电控组-123456"匹配"李许多"）
        5. card/nickname 包含 name           仅唯一命中采用，多命中视为失败
        6. None → 块照发，只写姓名，不标注「未匹配」（D22）
    """
    # 优先级 1：手工覆盖
    aliases = cfg.get("risk", {}).get("aliases", {})
    if name in aliases:
        return int(aliases[name])
    
    members_list = members(cfg, group_id)

    # 群昵称替换：每次匹配时热加载配置文件的 risk.name_map，把 card/nickname 中的旧名替换为新名
    import json
    try:
        with open(cfg["_config_path"], encoding="utf-8") as f:
            name_map = json.load(f).get("risk", {}).get("name_map", {})
    except (KeyError, OSError, ValueError):
        name_map = cfg.get("risk", {}).get("name_map", {})
    if name_map:
        replaced = []
        for m in members_list:
            m = dict(m)
            for field in ("card", "nickname"):
                text = m.get(field) or ""
                for old, new in name_map.items():
                    text = text.replace(old, new)
                m[field] = text
            replaced.append(m)
        members_list = replaced

    # 优先级 2：群名片精确匹配
    for m in members_list:
        if m.get("card") == name:
            return int(m["user_id"])
    
    # 优先级 3：昵称精确匹配
    for m in members_list:
        if m.get("nickname") == name:
            return int(m["user_id"])
    
    # 优先级 4：模糊匹配（群昵称类似"李许多-电控组-123456"）
    fuzzy_matches = []
    for m in members_list:
        card = m.get("card") or ""
        nickname = m.get("nickname") or ""
        if card.startswith(name + "-") or nickname.startswith(name + "-"):
            fuzzy_matches.append(int(m["user_id"]))
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]
    
    # 优先级 5：包含匹配（仅唯一）
    matches = []
    for m in members_list:
        if name in (m.get("card") or "") or name in (m.get("nickname") or ""):
            matches.append(int(m["user_id"]))
    if len(matches) == 1:
        return matches[0]
    
    # 优先级 6：返回 None
    return None


def send(cfg: dict, target: str, text: str) -> int:
    """`target` 是群号或 "private:<qq>"。返回 message_id。

    text 中的 `\x00at:<qq>\x00` 会在原位置转成 @ 段，其余按文本段发送。
    """
    import re

    message: list[dict] = []
    for i, part in enumerate(re.split(r"\x00at:(\d+)\x00", text)):
        if i % 2 == 1:
            message.append({"type": "at", "data": {"qq": part}})
        elif part:
            message.append({"type": "text", "data": {"text": part}})

    if target.startswith("private:"):
        user_id = int(target.split(":", 1)[1])
        params = {"user_id": user_id, "message": message}
        result = api(cfg, "send_private_msg", params)
    else:
        group_id = int(target)
        params = {"group_id": group_id, "message": message}
        result = api(cfg, "send_group_msg", params)
    
    return int(result.get("message_id", 0))
