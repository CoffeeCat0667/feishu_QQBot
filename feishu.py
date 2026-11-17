"""飞书多维表格 → 内存（不落盘）。

复用 `ThirdParty/feishu_export/feishu_export.py` 的四个函数，零改动：
`BitableClient` / `list_tables` / `list_fields` / `iter_records`。

返回结构（后面全用它，不再包类）：

    [{"name": "研发进展总表",
      "fields": ("任务名称", "任务负责人", ...),
      "records": ({"任务名称": "...", ...}, ...)}, ...]

坑：`iter_records` 会往 stdout 打进度 → 重定向到 stderr。
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

THIRD_PARTY = Path(__file__).resolve().parent / "ThirdParty" / "feishu_export"


def fetch(cfg: dict) -> list[dict]:
    """读导出配置 → 列出全部表 → 逐表拉全量 records。

    TODO M2：
      1. `sys.path.insert(0, str(THIRD_PARTY))` 后 `import feishu_export`；
      2. 读 `cfg["feishu"]["config_path"]`（含 app_token / personal_base_token）；
      3. `list_tables` + `list_fields` + `iter_records(page_size=500)`；
      4. 忽略导出配置里的 `view_id`（D5）；
      5. 任何异常 → `RuntimeError("fetch: ...")`，整轮中止（不发半套数据）。
    """
    raise NotImplementedError("TODO M2: 拉取飞书全表")


def read_config(path: str | Path) -> dict:
    """读 `feishu_export_config.json`（app_token / personal_base_token / page_size）。"""
    raise NotImplementedError("TODO M2: 读飞书导出配置")


@contextlib.contextmanager
def quiet_stdout():
    """`iter_records` 的进度输出赶到 stderr，别污染日志正文。

        with quiet_stdout():
            records = list(iter_records(...))
    """
    raise NotImplementedError("TODO M2: 重定向 stdout")
