#!/usr/bin/env python3
"""依赖自检（骨架，未核验）。

用途：在任何计算或答题前确认运行环境满足要求。
行为：只检查，不安装、不修改环境；缺失即 FATAL 并以非零码退出。
"""

from __future__ import annotations

import importlib
import json
import os
import platform
import sys

REQUIRED = {
    "numpy": None,
    "pandas": None,
    "sympy": None,
}
OPTIONAL = {"scipy": None}

VENDOR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor")

FATAL_TEMPLATE = (
    "FATAL: 依赖缺失 — {missing}\n"
    "  interpreter: {interpreter}\n"
    "  python: {pyver}\n"
    "  说明: 本技能不安装任何依赖，也不降级为口算或记忆作答。\n"
    "  处理: 请环境方在 {interpreter} 下补齐依赖后重试（参见 references/dependencies.md）。\n"
)


def main() -> int:
    result = {
        "interpreter": sys.executable,
        "python": platform.python_version(),
        "required": {},
        "optional": {},
        "vendor": {},
        "status": "ok",
    }
    missing = []
    for name in REQUIRED:
        try:
            mod = importlib.import_module(name)
            result["required"][name] = getattr(mod, "__version__", "unknown")
        except Exception as exc:  # noqa: BLE001
            result["required"][name] = f"MISSING ({type(exc).__name__})"
            missing.append(name)
    for name in OPTIONAL:
        try:
            mod = importlib.import_module(name)
            result["optional"][name] = getattr(mod, "__version__", "unknown")
        except Exception as exc:  # noqa: BLE001
            result["optional"][name] = f"missing ({type(exc).__name__})"

    sys.dont_write_bytecode = True  # 不在 vendor/ 内产生 __pycache__
    sys.path.insert(0, VENDOR_DIR)
    try:
        vendor = importlib.import_module("chemlib")
        result["vendor"]["chemlib"] = {
            "path": vendor.__file__,
            "version": "2.2.4 (vendored, unmodified)",
            "status": "unchecked",
        }
    except Exception as exc:  # noqa: BLE001
        result["vendor"]["chemlib"] = {"path": VENDOR_DIR, "error": f"{type(exc).__name__}: {exc}"}
        missing.append("vendor/chemlib")

    if missing:
        result["status"] = "FATAL"
        print(
            FATAL_TEMPLATE.format(
                missing=", ".join(missing),
                interpreter=sys.executable,
                pyver=platform.python_version(),
            ),
            file=sys.stderr,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
