#!/usr/bin/env python3
"""zlinglong 计算入口（骨架，未核验）。

已实现的最小命令：deps / mass / balance。
其余子命令为占位：调用即返回明确的未实现说明与对应推迟条目，不做任何计算。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

VENDOR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor")
sys.path.insert(0, VENDOR_DIR)
sys.dont_write_bytecode = True  # 保持 vendor/ 与原包逐字节一致，不产生 __pycache__

from chemlib import Compound, Reaction  # noqa: E402  (vendored engine)

STUB_NOTES = {
    "solution": "占位：溶液浓度/稀释封装待实现（未核验）",
    "equilibrium": "占位：平衡常数与转化率需扩展模块（见 scripts/extensions/equilibrium.py）",
    "acidbase": "占位：弱电解质电离需扩展模块（未核验）",
    "ksp": "占位：沉淀溶解平衡需扩展模块（未核验）",
    "thermo": "占位：热化学封装待实现（未核验）",
    "kinetics": "占位：速率相关能力见 scripts/extensions/kinetics.py（未核验）",
    "ions": "推迟（D-1）：离子/电荷相关能力已推迟，本次不计算",
    "electrochem": "推迟（D-1）：电化学定量能力已推迟，本次不计算",
}


def _emit(payload: dict, as_json: bool) -> int:
    payload.setdefault("engine", "vendor/chemlib 2.2.4 (unmodified, unchecked)")
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0 if payload.get("ok", True) else 1


def cmd_deps(args: argparse.Namespace) -> int:
    os.execv(sys.executable, [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "deps_check.py")])


def cmd_mass(args: argparse.Namespace) -> int:
    compound = Compound(args.formula)
    return _emit(
        {
            "ok": True,
            "command": "mass",
            "formula_in": args.formula,
            "molar_mass": compound.molar_mass(),
            "formula_engine": compound.formula,
            "warning": "使用 chemlib 内置 IUPAC 原子量；教材附表取值可能不同（D-2），附录中须提示差异",
            "unchecked": True,
        },
        args.json,
    )


def cmd_balance(args: argparse.Namespace) -> int:
    reaction = Reaction.by_formula(args.equation)
    reaction.balance()
    return _emit(
        {
            "ok": True,
            "command": "balance",
            "equation_in": args.equation,
            "balanced_engine_form": reaction.formula,
            "warning": "chemlib 输出的化学式为扁平记号，展示时必须改写为教材记号（D-2）",
            "deferred": "带电荷的离子方程式属 D-1，本次不处理",
            "unchecked": True,
        },
        args.json,
    )


def cmd_stub(args: argparse.Namespace) -> int:
    return _emit(
        {
            "ok": False,
            "command": args.command,
            "note": STUB_NOTES.get(args.command, "占位命令未实现"),
            "unchecked": True,
        },
        args.json,
    )


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="输出 JSON（附录据此生成 sources 字段）")

    parser = argparse.ArgumentParser(prog="chembox", description="zlinglong 计算入口（骨架，未核验）")
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("deps", parents=[common], help="依赖自检（转调 deps_check.py）")

    mass = sub.add_parser("mass", parents=[common], help="摩尔质量（已实现，未核验）")
    mass.add_argument("--formula", required=True)
    mass.set_defaults(func=cmd_mass)

    balance = sub.add_parser("balance", parents=[common], help="配平（已实现，未核验；不支持带电荷离子）")
    balance.add_argument("--equation", required=True)
    balance.set_defaults(func=cmd_balance)

    for name, help_text in STUB_NOTES.items():
        stub = sub.add_parser(name, parents=[common], help=help_text)
        stub.set_defaults(func=cmd_stub)

    sub.choices["deps"].set_defaults(func=cmd_deps)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
