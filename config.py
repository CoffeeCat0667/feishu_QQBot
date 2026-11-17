"""配置：JSON → dict，默认值 + 必填校验。

只有 12 项真会变的东西，其余一律写死在代码里：
触发时间、state 路径、NapCat 地址/token/WebUI、目标群、管理员 QQ、
飞书配置路径与任务表名、LLM 三件套、提示词、风险天数与别名。

`config.json` 含密钥，已在 `.gitignore` 中；模板见 `config_example.json`。
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULTS: dict = {
    "times": ["09:00", "18:00"],
    "state_path": "state.json",
    "napcat": {
        "api": "http://127.0.0.1:3000",
        "token": "",
        "webui": "http://127.0.0.1:6099",
        "webui_hash": "",
    },
    "target": {"group": ""},
    "admin": 0,
    "feishu": {
        "config_path": "ThirdParty/feishu_export/feishu_export_config.json",
        "task_table": "研发进展总表",
    },
    "llm": {
        "api_key": "",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    "prompt": {"persona": "", "style": "", "output_format": "", "task_hint": ""},
    "risk": {"near_days": 5, "idle_days": 15, "aliases": {}},
}

REQUIRED = (
    "napcat.token",
    "napcat.api",
    "target.group",
    "admin",
    "llm.api_key",
    "llm.base_url",
    "llm.model",
    "feishu.config_path",
)


def load(path: str | Path = "config.json") -> dict:
    """读 JSON → 用 DEFAULTS 递归补缺 → 校验 REQUIRED → 返回 dict。

    TODO M1：缺字段报 `ValueError("缺少配置项: xxx")`，不要静默给空值；
    `target.group` 可以是群号或群名，两者都非空才算配置完整。
    """
    raise NotImplementedError("TODO M1: load()")


def dig(cfg: dict, dotted: str, default=None):
    """`dig(cfg, "llm.model")` → 嵌套取值，取不到返回 default。"""
    raise NotImplementedError("TODO M1: dig()")
