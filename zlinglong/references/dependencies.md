# 运行时依赖与版本

## 运行环境（2026-09-15 实测）

- 解释器：`/home/hibiscus/miniforge3/bin/python`（Python 3.12.10）。
- 计算引擎：`vendor/chemlib/`（chemlib 2.2.4 原样副本，随包，无需安装）。
- 依赖库：numpy 2.3.2、pandas 3.0.5、sympy 1.14.0（chemlib 源码所需）；scipy 1.18.1 供后续扩展模块使用。
- 可选：Pillow 12.3.0——仅电化学图渲染路径使用，属推迟移除项 D-2。
- 不随运行时使用：chempy 0.10.1（BSD-2-Clause）、mendeleev 1.3.0（MIT）、pint 0.24.4——仅作构建期参考与数据生成来源，脚本不得在运行时 import。

## 依赖自检

- 入口：`python scripts/deps_check.py`。
- 任一项缺失时输出 FATAL 模板并以非零码退出，内容包括缺失项、期望版本、解释器路径与安装责任方（环境方）。
- 自检不安装任何包、不修改环境。

## vendored chemlib 完整性（sha256）

| 文件 | sha256 |
|------|--------|
| `__init__.py` | a0cb382ad2f68585907a3977422324bcbd4095d5e4be855b35da2c1551b0f31b |
| `chemistry.py` | 6294bb5d53d87bd26fd08f90f2c23f45df26c3d2491d52430b31a2f1fac5e0dc |
| `constants.py` | 2bc85122c678cbeba236fd2164a314acb2014802cb337154a208df2ca49bea62 |
| `electrochemistry.py` | 0dedeb5b17135980c27845a75813646b3e370426c5d563dd6e0419a2a99f93bd |
| `parse.py` | 67603f3db3e8c9a0931e64120f0b194ec03f01556d39524126e17ca658f65ebe |
| `quantum_mechanics.py` | 686073fb1803a5b5c98fabc7947d9f4e86dcaa4f3a8af9696dc495bd9fc5ef01 |
| `thermochemistry.py` | d0e5fed8107b2460e154e21d833a7abeda4157b5378e3b031daabb9225ff97da |
| `utils.py` | 9ed751db450607ad3ef6b53c5a475d96a6180e42bf77fbf689f004f16cba04ed |
| `resources/PTE.csv` | 20618b52da4e5deaed6d701fab70f97063456e72bb7090bcba474a643761e72c |
| `resources/thermochemistry.csv` | 3a31eda730f235e3b0170b2519d48ef28d0e399ca2c2c296907c76fb6a683d4e |
| `resources/gcell_root.png` | 0af49429189fefbb21b709187698a5ae9cb9952c67247cbf2e0d5de8a4abcb89 |
| `LICENSE.txt` | d30aea107dcec5b246da625c743c94b78a974cbb1c4c1e75e89727ef9ed4fa8a |
