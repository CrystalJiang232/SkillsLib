"""扩展模块：平衡常数与转化率（占位，未核验）。

缺口来源：chemlib 仅有 ICE 表助手 Reaction.equilibrium_concentrations，
不含由 K 求解平衡组成的能力；ChemPy 的 Equilibrium 依赖 sym/pyneqsys，成本高。
实现方向（待定稿）：面向高中范围的溶质守恒 + 质量作用方程数值解（numpy/scipy）。
"""


def equilibrium_constant(*args, **kwargs):
    raise NotImplementedError(
        "未实现（未核验）：平衡常数计算。见 references/deferrals.md D-4；"
        "实现前遇到此类题目返回「知识库未收录（能力未实现）」。"
    )


def conversion_from_k(*args, **kwargs):
    raise NotImplementedError("未实现（未核验）：由 K 求转化率。")
