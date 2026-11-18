"""配置：JSON → dict，默认值 + 必填校验。

只有 13 项真会变的东西，其余一律写死在代码里：
触发时间、state 路径、NTP 服务器、NapCat 地址/token、目标群、管理员 QQ、
飞书导出配置路径、LLM 三件套、提示词、风险天数与别名。

`config.json` 含密钥，已在 `.gitignore` 中；模板见 `config_example.json`。
"""

from __future__ import annotations

from copy import deepcopy
import datetime as dt
import json
from pathlib import Path

DEFAULTS: dict = {
    "times": ["09:00", "18:00"],
    "state_path": "state.json",
    "ntp_servers": ["ntp.aliyun.com", "ntp.tencent.com"],
    "napcat": {
        "api": "http://127.0.0.1:3000",
        "token": "",
    },
    "target": {"group": ""},
    "admin": 0,
    "feishu": {
        "config_path": "ThirdParty/feishu_export/feishu_export_config.json",
    },
    "llm": {
        "api_key": "",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    "prompt": {"persona": "", "style": "", "output_format": "", "task_hint": ""},
    "risk": {"near_days": 5, "idle_days": 15, "aliases": {}, "name_map": {}},
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


def load(path: str | Path = Path(__file__).with_name("config.json")) -> dict:
    """读配置、补默认值并校验 M1 所需字段。"""
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as f:
            supplied = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取配置 {path}: {exc}") from exc

    if not isinstance(supplied, dict):
        raise ValueError("配置顶层必须是 JSON 对象")

    missing = []
    for dotted in REQUIRED:
        value = supplied
        for key in dotted.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if not value:
            missing.append(dotted)
    if missing:
        raise ValueError("缺少配置项: " + ", ".join(missing))

    cfg = deepcopy(DEFAULTS)

    def merge(defaults: dict, values: dict) -> None:
        for key, value in values.items():
            if isinstance(defaults.get(key), dict) and isinstance(value, dict):
                merge(defaults[key], value)
            else:
                defaults[key] = value

    merge(cfg, supplied)

    if isinstance(cfg["admin"], bool) or not str(cfg["admin"]).isdigit() or int(cfg["admin"]) <= 0:
        raise ValueError("配置项 admin 必须是正整数")

    times = cfg["times"]
    if not isinstance(times, list) or not times:
        raise ValueError("配置项 times 必须是非空数组")
    normalized_times = []
    for value in times:
        if not isinstance(value, str):
            raise ValueError("times 中的每项必须是 HH:MM 或 HH:MM:SS")
        value = value.replace("：", ":")
        parsed = None
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                parsed = dt.datetime.strptime(value, fmt)
                if parsed.strftime(fmt) == value:
                    break
                parsed = None
            except ValueError:
                pass
        if parsed is None:
            raise ValueError(f"无效触发时间: {value!r}（应为 HH:MM 或 HH:MM:SS）")
        normalized_times.append(value)
    cfg["times"] = normalized_times

    cfg["_config_path"] = str(path.resolve())
    return cfg
