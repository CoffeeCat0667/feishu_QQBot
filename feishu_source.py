"""飞书多维表格 → 内存 Snapshot（PLAN §5.3）。

I/O 模块。复用 `ThirdParty/feishu_export/feishu_export.py` 的公共函数，零改动：

    BitableClient / list_tables / list_fields / iter_records

两条硬约束：
  1. **不写任何文件**，只在内存里拼 Snapshot；
  2. 任一表失败 → 抛 StageError，整轮中止（不发半套数据）。

坑（§11）：
  - `iter_records` 会往 stdout 打进度 → 运行期重定向进 debug 日志；
  - 忽略导出配置里的 `view_id`（D5），记录一条 INFO。
"""

from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from models import DataSource, Snapshot, StageError, TableData

THIRD_PARTY = Path(__file__).resolve().parent / "ThirdParty" / "feishu_export"


class FeishuSource(DataSource):
    """一次运行拉一次全表。无缓存——数据每天都在变。"""

    def __init__(self, feishu_cfg: object) -> None:
        self._cfg = feishu_cfg

    def fetch(self, cfg: object = None) -> Snapshot:
        """读导出配置 → 列出全部表 → 逐表拉全量 records。

        TODO M2：
          1. `sys.path.insert(0, str(THIRD_PARTY))` 后 import feishu_export；
          2. 读 `self._cfg.config_path`（含 app_token / personal_base_token）；
          3. `list_tables` 拿表名，`list_fields` 拿列名，`iter_records` 拿行；
          4. 包装成 TableData，最后拼 Snapshot(now, tables)；
          5. 任何异常 → `raise StageError("fetch", ...)`，保留原始堆栈到 cause。
        """
        raise NotImplementedError("TODO M2: 拉取飞书全表")


class _StdoutToStderr:
    """把 `iter_records` 的进度输出赶到 stderr，避免污染控制台/日志正文。"""

    def __enter__(self) -> "_StdoutToStderr":
        raise NotImplementedError("TODO M2: 重定向 stdout")

    def __exit__(self, *exc: object) -> bool:
        raise NotImplementedError("TODO M2: 恢复 stdout")
