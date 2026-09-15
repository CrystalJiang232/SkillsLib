# 推迟事项登记表（deferrals）

> 本文件是本技能「未完成但已决定推迟」的单一登记处；任何推迟能力被触发时，回答必须引用本文件的条目编号。

## D-1 离子/电荷相关与电化学 —— 推迟（用户 2026-09-15 指示）

- 范围：离子方程式书写与配平、电荷守恒、溶液中的离子行为、原电池与电解池的定量计算、依赖离子浓度的 Nernst 计算。
- 原因：chemlib 2.2.4 没有离子/电荷模型（`Compound('SO4')` 解析为 `S1O4`，无电荷信息），唯一可用的电极电势表仅 21 条，且电化学模块的图渲染路径依赖 PIL。
- 影响：模块 2（解题）与模块 3（过程分析）遇到离子相关题面时，只能输出「知识库未收录（该能力推迟）」，并给出教材条目的 `file:line` 作为背景，不得给出自算数值。
- 恢复条件：扩展模块 `scripts/extensions/ions.py` 与电化学路径完成实现与核验，并在本文件登记证据。

## D-2 chemlib 值调整 —— 推迟

- 范围：把 `vendor/chemlib/resources/PTE.csv` 的 `AtomicMass` 补一列教材取值、修正 `Valence` 列语义、移除 electrochemistry 的 PIL 图渲染路径与 `gcell_root.png`、公式显示改为教材记号、包重命名。
- 现状：`vendor/chemlib/` 与上游 2.2.4 逐字节一致（sha256 清单见 `references/dependencies.md`）。
- 影响：当前 `Compound.molar_mass()` 使用 IUPAC 值（如 S 32.065、Cl 35.453），与教材附表取值（32、35.5）不一致；该差异必须在附录中显式提示。

## D-3 教材 PDF 迁移 —— 推迟

- 范围：从用户提供的教材 PDF 提取数据与原理条目，写入 `data/` 与 `knowledge/`。
- 现状（2026-09-15 更新）：五个容器 `~/ref/{1..5}.edupdf` 已到位（共 79.5 MB），但每个容器都是 ZipCrypto 加密的 zip，内含单个 `document.pdf`（12241298–22093382 B），当前无法解包（`unzip -t -P ""` 报 incorrect password；文件与目录中均无密码线索）。
- 渲染链路已就绪：`/usr/bin/gs` 可渲染为 PNG 并可提取文本（已用无关 PDF 实测通过）；环境中仍无 `pdftotext`／`pypdf`／`pdfplumber`／`pdfminer`／`fitz`。
- 目标位置：`zlinglong/textbook/`（命名与清单元数据见该目录内 `MANIFEST.md`）。
- 影响：`data/` 与 `knowledge/` 目前全部为占位，不得作为作答依据。

## D-4 数值核验集 —— 不提供（Z-A 决定）

- 现状：不建立金标准题集；因此计算脚本的正确性没有独立可执行证据。
- 影响：`scripts/` 全部函数默认标注「未核验」，直到后续阶段提供核验证据。
