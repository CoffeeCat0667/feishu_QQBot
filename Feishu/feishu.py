"""飞书全表到内存（不落盘）。

复用 `ThirdParty/feishu_export/feishu_export.py` 的客户端和接口。
返回内存字典 {table_id: {"name": str, "records": [{...}, ...]}, ...}。
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import Any

THIRD_PARTY = Path(__file__).resolve().parents[1] / "ThirdParty" / "feishu_export"


def fetch(cfg: dict) -> dict[str, dict[str, Any]]:
    """读导出配置，拉取全部表的全量记录到内存。
    
    返回 {table_id: {"name": str, "records": [{fields}, ...]}, ...}
    
    异常 → RuntimeError，整轮中止。
    """
    try:
        # 导入 feishu_export
        if str(THIRD_PARTY) not in sys.path:
            sys.path.insert(0, str(THIRD_PARTY))
        import feishu_export

        config_path = Path(cfg["feishu"]["config_path"])
        if not config_path.exists():
            raise FileNotFoundError(f"导出配置不存在: {config_path}")

        with config_path.open(encoding="utf-8") as f:
            export_cfg = json.load(f)

        app_token = export_cfg.get("app_token", "")
        personal_base_token = export_cfg.get("personal_base_token", "")
        domain = export_cfg.get("domain", feishu_export.DEFAULT_DOMAIN)
        page_size = int(export_cfg.get("page_size", 500))
        delay = float(export_cfg.get("delay", 0.1))
        tables = export_cfg.get("tables", [])

        if not app_token or not personal_base_token:
            raise ValueError("导出配置缺少 app_token 或 personal_base_token")

        client = feishu_export.BitableClient(personal_base_token, domain)
        result: dict[str, dict[str, Any]] = {}

        for table_spec in tables:
            table_id = table_spec.get("table_id", "")
            if not table_id:
                continue

            table_name = table_spec.get("name", table_id)
            view_id = table_spec.get("view_id", None)

            # 列出字段
            fields = feishu_export.list_fields(client, app_token, table_id)
            field_names = [f.get("field_name") for f in fields if f.get("field_name")]

            # 迭代记录，展开嵌套值
            records: list[dict[str, Any]] = []
            with quiet_stdout():
                for record in feishu_export.iter_records(
                    client,
                    app_token,
                    table_id,
                    view_id,
                    field_names,
                    page_size,
                    delay,
                ):
                    flattened = {}
                    for key, value in (record.get("fields") or {}).items():
                        flattened[key] = feishu_export.flatten_value(value)
                    records.append(flattened)

            result[table_id] = {"name": table_name, "records": records}

        # 全量归一化：所有表所有记录里的"待审核"替换为"进行中"
        for td in result.values():
            for rec in td["records"]:
                for k, v in rec.items():
                    if v == "待审核":
                        rec[k] = "进行中"

        return result

    except Exception as exc:
        raise RuntimeError(f"fetch: {exc}") from exc


@contextlib.contextmanager
def quiet_stdout():
    """iter_records 的进度输出重定向到 stderr，避免污染日志。"""
    old_stdout = sys.stdout
    try:
        sys.stdout = sys.stderr
        yield
    finally:
        sys.stdout = old_stdout
