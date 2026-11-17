"""NapCat OneBot v11 HTTP 客户端（PLAN §5.8）。

I/O 模块。三件事都在这里：
  1. 名称解析（群名 / 好友名 → id）；
  2. 群成员拉取 + 姓名 → QQ 匹配（Q9 默认：不单独拆 Directory）；
  3. 发消息（群 / 私聊）。

协议：`POST {api_base}/{action}`，JSON body 即 params，头 `Authorization: Bearer {token}`。
消息段用 array 格式（`messagePostFormat=array`）：
    [{"type": "at", "data": {"qq": "123"}},
     {"type": "text", "data": {"text": " 的进度风险：..."}}]

已实测的坑（§11）：
  - `get_group_list` 不完整（2 个群只返回 1 个）→ 必须用 `get_recent_contact` 兜底；
  - 中文必须显式 UTF-8（requests 默认可以）；
  - token 为空时 NapCat 不校验来源 —— 不要留空。
"""

from __future__ import annotations

from models import Member, OutMessage, ResolvedTarget, Sender, TargetSpec


class NapCatClient(Sender):
    def __init__(self, napcat_cfg: object) -> None:
        self._cfg = napcat_cfg
        self._session = None

    # ---- 底层 -----------------------------------------------------------

    def call(self, action: str, params: dict | None = None, *, timeout: float | None = None) -> dict:
        """调一个 OneBot action。retcode != 0 抛 StageError("napcat", ...)。

        TODO M3：requests.Session + 重试（napcat.retries / retry_backoff_seconds）。
        """
        raise NotImplementedError("TODO M3: OneBot 调用")

    # ---- Sender 接口 ----------------------------------------------------

    def resolve_target(self, spec: TargetSpec) -> ResolvedTarget:
        """群名/好友名 → id。降级链（已在旧代码里验证过）：

            显式别名(group_aliases) → 纯数字 ID → get_group_list → get_recent_contact
            好友：get_friend_list(nickname / remark) → get_recent_contact
        """
        raise NotImplementedError("TODO M3: 名称解析")

    def members(self, group_id: int) -> list[Member]:
        """群成员列表。每次运行拉一次即可（运行间隔 9 小时，缓存无意义）。"""
        raise NotImplementedError("TODO M3: 拉群成员")

    def send(self, target: ResolvedTarget, message: OutMessage) -> int:
        """发一条消息，返回 message_id。at_qq 非空时自动补 at 段。"""
        raise NotImplementedError("TODO M3: 发送")

    # ---- 健康检查 -------------------------------------------------------

    def login_info(self) -> dict:
        raise NotImplementedError("TODO M3: get_login_info")


# --------------------------------------------------------------------------
# 姓名 → QQ
# --------------------------------------------------------------------------

def match_member(name: str, members: list[Member], aliases: dict[str, int]) -> int | None:
    """匹配链（D11），命中即返回：

        1. aliases[name]                → 手工覆盖，最高优先级
        2. 群名片(card) == name
        3. 昵称(nickname) == name
        4. card/nickname 包含 name      → 仅唯一命中才采用，多命中视为失败
        5. 全部失败 → None（块照发，只写姓名，D22）
    """
    raise NotImplementedError("TODO M3: 姓名匹配")


def to_segments(message: OutMessage) -> list[dict]:
    """OutMessage → OneBot array 段。"""
    raise NotImplementedError("TODO M3: 消息段")
