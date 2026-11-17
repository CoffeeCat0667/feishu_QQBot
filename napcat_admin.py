"""NapCat WebUI 接口：把 `napcat.http_server` 推送到 NapCat（PLAN §5.8 / §11）。

I/O 模块，只在 `--provision` 时被调用。

已实测的坑，别踩第二遍：
  - `GET /api/.../GetConfig` 返回 404 → **必须 POST**；
  - `SetConfig` 的 body 是 `{"config": "<JSON 字符串>"}`，直接传对象会报
    `JSON5: invalid character 'o'`；
  - 登录：`POST /api/auth/login {"hash": "<login_hash>"}` → 返回 `Credential`，
    后续请求带 `Authorization: Bearer <Credential>`；
  - WebUI 的 token（6099 那套）**不能**用于 OneBot API，两者无关。
"""

from __future__ import annotations

from typing import Any


def provision(napcat_cfg: object, *, dry_run: bool = False) -> dict[str, Any]:
    """读取 `config.json` 的 `napcat.http_server`（全字段），推送到 NapCat 并回读校验。

    TODO M1（沿用已验证实现）：
      1. 登录拿 Credential；
      2. POST GetConfig 读当前 network 配置；
      3. 按 name 覆盖/追加 httpServers[]；
      4. SetConfig（config 字段传字符串）；
      5. 再 GetConfig 回读，逐字段比对；
      6. dry_run 只打印 diff，不写。

    返回：{"changed": bool, "before": {...}, "after": {...}, "verified": bool}
    """
    raise NotImplementedError("TODO M1: WebUI 推送")


def login(webui_cfg: object) -> str:
    """`POST {base_url}/api/auth/login` → Credential。"""
    raise NotImplementedError("TODO M1: WebUI 登录")
