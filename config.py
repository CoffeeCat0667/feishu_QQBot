"""配置加载、校验与环境变量覆盖。

纯模块：读 JSON、返回 frozen dataclass，不碰网络、不写文件。
配置字段的唯一说明见 PLAN §3 与 config_example.json。

依赖方向：config ← main / pipeline / 各 I/O 模块（它们只接收自己那段配置）
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from models import TargetSpec

ENV_LLM_API_KEY = "QQBOT_LLM_API_KEY"
ENV_NAPCAT_TOKEN = "QQBOT_NAPCAT_TOKEN"


# --------------------------------------------------------------------------
# schedule —— 触发
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ScheduleConfig:
    utc8_times: tuple[str, ...] = ("09:00", "18:00")   # "HH:MM" 或 "HH:MM:SS"
    tolerance_seconds: int = 30                        # ±30s 窗口
    poll_interval_seconds: int = 5
    run_once_on_start: bool = True                     # 首启立即跑一次（D9）
    suppress_after_run_seconds: int = 120              # 手动跑后抑制窗口
    state_path: str = "state.json"                     # Q5 默认：相对运行目录


# --------------------------------------------------------------------------
# time_sync —— 校时
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TimeSyncConfig:
    mode: str = "ntp"                                  # "ntp" | "system"
    ntp_servers: tuple[str, ...] = ()
    ntp_timeout_seconds: int = 3
    resync_minutes: int = 30
    http_fallback: bool = True
    http_fallback_urls: tuple[str, ...] = ()
    on_total_failure: str = "skip"                     # "skip" | "system"


# --------------------------------------------------------------------------
# napcat —— OneBot HTTP 与 WebUI
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class NapCatConnectConfig:
    scheme: str = "http"
    host: str = "127.0.0.1"
    api_base: str = ""                                 # 非空则完全覆盖 scheme/host/port

    def base_url(self, port: int) -> str:
        """程序实际连接的地址。api_base 优先，否则 scheme://host:port。"""
        raise NotImplementedError("TODO M1: 拼接 base_url")


@dataclass(frozen=True)
class NapCatWebUIConfig:
    base_url: str = "http://127.0.0.1:6099"
    login_hash: str = ""                               # 仅 --provision 用


@dataclass(frozen=True)
class NapCatConfig:
    http_server: dict[str, Any] = field(default_factory=dict)   # 原样镜像 napcat.httpServers[]
    connect: NapCatConnectConfig = field(default_factory=NapCatConnectConfig)
    webui: NapCatWebUIConfig = field(default_factory=NapCatWebUIConfig)
    timeout_seconds: int = 15
    retries: int = 3
    retry_backoff_seconds: float = 1.0
    group_aliases: dict[str, str] = field(default_factory=dict)

    @property
    def token(self) -> str:
        return str(self.http_server.get("token") or "")

    @property
    def port(self) -> int:
        return int(self.http_server.get("port") or 3000)


# --------------------------------------------------------------------------
# 飞书
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class FeishuConfig:
    config_path: str = "ThirdParty/feishu_export/feishu_export_config.json"
    task_table_name: str = "研发进展总表"
    max_cell_chars: int = 300
    max_total_chars: int = 120000


# --------------------------------------------------------------------------
# LLM
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LLMConfig:
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model_id: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 4096
    request_timeout_seconds: int = 180
    retries: int = 2


@dataclass(frozen=True)
class PromptConfig:
    persona: str = ""
    style: str = ""
    output_format: str = ""
    task_hint: str = ""


# --------------------------------------------------------------------------
# 风险 / 发送 / 日志
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskConfig:
    near_days: int = 5
    idle_days: int = 15
    owner_aliases: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SendConfig:
    max_chars_per_message: int = 800
    interval_ms: int = 1500
    strip_markdown: bool = True


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    batch_seconds: int = 10
    flush_on_error: bool = True
    max_chars_per_report: int = 3000


# --------------------------------------------------------------------------
# 顶层
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Config:
    source_path: Path
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    time_sync: TimeSyncConfig = field(default_factory=TimeSyncConfig)
    napcat: NapCatConfig = field(default_factory=NapCatConfig)
    targets: tuple[TargetSpec, ...] = ()
    admin: tuple[TargetSpec, ...] = ()
    feishu: FeishuConfig = field(default_factory=FeishuConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    prompt: PromptConfig = field(default_factory=PromptConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    send: SendConfig = field(default_factory=SendConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def load_config(path: str | Path = "config.json") -> Config:
    """读 JSON → 校验 → 环境变量覆盖 → Config。

    校验失败直接抛 ValueError，附带字段名与期望类型（不要静默纠正）。
    TODO M1：按 §3 实现，含 mask_secret() 打码与必填项检查。
    """
    raise NotImplementedError("TODO M1: 配置加载")


def mask_secret(secret: str, keep: int = 4) -> str:
    """`507a592c...4453` 这样的打码形式，日志与 --check 输出都用它。"""
    raise NotImplementedError("TODO M1: 密钥打码")
