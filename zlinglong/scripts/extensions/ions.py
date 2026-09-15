"""扩展模块：离子与电荷 —— 推迟（D-1，未核验）。

本模块整体属于推迟项 D-1：chemlib 无离子/电荷模型（Compound('SO4') 解析为 S1O4）。
在解除推迟前，任何依赖离子电荷的计算都必须返回「知识库未收录（能力推迟）」。
"""


def parse_ion(*args, **kwargs):
    raise NotImplementedError("推迟（D-1）：离子解析与电荷模型尚未实现。")


def ionic_charge_balance(*args, **kwargs):
    raise NotImplementedError("推迟（D-1）：电荷守恒校验尚未实现。")
