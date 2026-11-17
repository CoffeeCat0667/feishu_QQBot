"""无网络自测入口（标准库 unittest，零第三方依赖）。

    python selftest.py              # 发现并跑全部 test_*.py
    python selftest.py -v           # 详细输出
    python selftest.py test_analysis.py::TestOverdue   # 跑单个用例

约定：`test_*.py` 与被测模块**同级平铺**在根目录（见 PLAN §4）。
自测只覆盖纯模块：scheduler / analysis / blocks / splitter / render。
I/O 模块（clock / feishu_source / agent / napcat）需要网络或桩件，不进 selftest。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    verbosity = 2 if ("-v" in argv) else 1
    argv = [a for a in argv if a != "-v"]

    if argv:                                   # 传了具体模块
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromNames(argv)
    else:
        suite = unittest.TestLoader().discover(str(ROOT), pattern="test_*.py")

    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    print(
        "\n合计 %d 个用例：失败 %d，错误 %d，跳过 %d"
        % (result.testsRun, len(result.failures), len(result.errors), len(result.skipped))
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
