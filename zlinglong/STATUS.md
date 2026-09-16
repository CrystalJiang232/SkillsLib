# zlinglong 状态与交接（STATUS）

> 本文件是**给其他 agent 会话看的可见状态页**：`.agent/` 位于仓库忽略目录，其他会话可能看不到，因此本文件承载该状态的可见子集。
> 最近更新：2026-09-16（第三轮：状态分仓）｜ 对应提交：`d0840e6 zll-0.5`｜ 工作树：本轮改动未提交（`.gitignore`、`README.md`、本文件）
> 状态位置（2026-09-16 起）：zlinglong 的全部状态文件在 **`zlinglong/.agent/state/`**；父级 `.agent/state/` 仅存库级状态（跨技能决策、仓库结构、打包与安装）。

## 1. 当前阶段

- 阶段：骨架（skeleton）已完成并入库；`vendor/chemlib/` 为 chemlib 2.2.4 原样副本，**尚未做值调整**（D-2 推迟）。
- 核验：全技能默认「未核验 / unchecked」（Z-A 决定，不设金标准题集）；除元素表外，`data/` 与 `knowledge/` 仍为占位，不得作为作答依据。
- 运行面：`chemlib`（随包）+ numpy/pandas/sympy；`chempy`、`mendeleev` 降级为构建期 oracle，脚本不得在运行时 import。
- 唯一阻塞：B-1 教材容器加密（见第 3 节）。
- 数据进展（2026-09-15/16）：`data/elements.jsonl` 已写入 47 条（周期 1–4 全量 + Rb/Sr/Ag/Sn/I/Ba/Au/Hg/Pb/Cs/Pt），sha256 `ab48093fed145a19995e2b6234daa7f6c0010b3270c6612c694832b31bc823f2`；教材取值现为**唯一真值来源**，PDF 复核语义已按用户指示移除。
- 脚本进展：**未改动**；`chembox` 与 `vendor/chemlib` 仍按 `resources/PTE.csv` 的 IUPAC 值计算，教材值尚未进入计算路径（待决 C-1）。
- git 状态（2026-09-16 第二轮复核）：HEAD `d0840e6 zll-0.5`，工作树干净；本节早前记录的「3 条未提交路径」已由该提交收编，不再是待决项。

## 2. 现在即可执行（不依赖教材 PDF）

| 编号 | 事项 | 命令 / 产出 | 状态 |
|------|------|-------------|------|
| N-1 | 依赖自检 | `python scripts/deps_check.py` | 已实测通过（numpy 2.3.2 / pandas 3.0.5 / sympy 1.14.0 / 可选 scipy 1.18.1） |
| N-2 | 已实现的计算入口 | `python scripts/chembox.py mass --formula H2SO4 --json`；`... balance --equation "Fe + O2 -> Fe2O3" --json` | 已实测通过；其余子命令为显式占位 |
| N-3 | 技能合法性校验 | `python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py zlinglong` | 预期输出 `Skill is valid!` |
| N-4 | 元素表写入 | 已用构建期 oracle（mendeleev 1.3.0 + `vendor/chemlib/resources/PTE.csv`）填 `mass_mendeleev`／`mass_chemlib`，`mass_textbook` 为用户确认的教材取值 | **已完成**（2026-09-15，47 条）；让教材值进入计算路径的后续修改见 C-1 |
| N-5 | 扩展模块实现 | 以 `scripts/extensions/equilibrium.py`、`kinetics.py` 替换 NotImplementedError（离子/电化学仍受 D-1 约束） | 可随时开始 |
| N-6 | 打包预演（可选） | `./package.sh` → `bin/zlinglong.skill`（`bin/` 属忽略目录） | 现无 PDF，包体约 0.4 MB；PDF 入库后显著变大（R11） |
| N-7 | 数值交叉核对层 | 用已安装的 pint 0.24.4 对脚本输出做量纲/量级核对 | 可随时开始 |

## 3. 阻塞项 B-1：教材容器加密

- 现象：`~/ref/{1..5}.edupdf` 均为 deflate zip，各含单个 `document.pdf`（12.2–22.1 MB）；`zipfile` 报 `flag_bits 0x801`（bit0 = 加密），`unzip` 报 `unable to get password`，`unzip -t -P ""` 报 `incorrect password`。
- 旁证：无 zip 注释；`*.edupdf:Zone.Identifier` 仅含 `ZoneId=3`；`~/ref`、`~/Downloads`、`~/Desktop`、`~/Documents` 中无密码说明；磁盘上无已解包的同名 PDF。
- 判断：容器级 ZipCrypto 口令保护（传统加密，非 AES）；原因**推测**与平台版权/DRM 有关，未经确认。
- 解除条件：提供口令，或直接提供已解包的 `document.pdf`（放置位置不限，随后由本技能复制入库）。
- 未做：没有尝试密码猜测、爆破或绕过保护。

## 4. 阻塞解除后立即可做（A 组）

| 编号 | 事项 | 做法 |
|------|------|------|
| A-1 | 解包并识别册次 | 解包至暂存目录；将每册第 1 页渲染为 PNG 目视确认册次，再按 `textbook/MANIFEST.md` 的命名约定复制进 `zlinglong/textbook/` |
| A-2 | **抓取附录快照**（本次提到的例子） | 对「相对原子质量表」「溶解性表」「电离常数/溶度积/标准电极电势表」逐页渲染 200–300 dpi PNG 存入 `zlinglong/textbook/snapshots/`，命名规则见 `textbook/MANIFEST.md` |
| A-3 | 数据导入 · 元素表 | 依 A-2 快照填 `data/elements.jsonl` 的 `mass_textbook`、`name_zh`，`source: 教材:<册次>#附录` |
| A-4 | 数据导入 · 其余表 | 同法填 `solubility.jsonl`、`valences.jsonl`、`constants.jsonl`、`series.jsonl`、`substances.jsonl` |
| A-5 | 原理条目迁移 | 写入 `knowledge/<册次>/*.md`，条目 `source` 精确到章节与页码 |
| A-6 | 解除未核验标记 | 每条核验后在 `references/deferrals.md` 登记证据，再移除该条的「未核验」标记 |

## 5. 通用注意事项

- 页码偏移：PDF 页序与印刷页码通常不一致（封面、前言、彩页），快照与来源必须同时记录两者。
- R3/R11：若容器加密属平台 DRM，把教材 PDF 打进 `.skill` 包分发可能与平台条款冲突（当前 Z-O 决定是随包），打包前需再确认。
- 可用工具：`/usr/bin/gs`（`-sDEVICE=png16m` 渲染、`-sDEVICE=txtwrite` 取文本）；环境无 `pdftotext`／`pypdf`／`pdfplumber`／`pdfminer`／`fitz`。
- 相关文档：推迟事项登记 `references/deferrals.md`；数据字段契约 `references/data-schema.md`；出处附录格式 `references/provenance-appendix.md`；四模块契约 `references/module-contracts.md`；依赖与 sha256 `references/dependencies.md`。

## 6. 恢复指引（新会话按序阅读）

1. 本文件（可见状态）。
2. `zlinglong/.agent/state/pending-clarifications.md` 的**第十二轮（2026-09-16）**与第十一轮：待决 C-1、C-2b 与已丢弃的 C-3~C-6 记录。
3. `zlinglong/.agent/state/constraints.md`（硬约束）、`todo.md`（任务）、`verification.md`（V18–V116 证据；库级的 V117 起在父级 `.agent/state/verification.md`）、`protection-status.md`（写入与备份登记）。

待决事项（恢复后第一件事）：C-1（教材值进入计算路径：运行时覆盖 / 烘焙进 CSV / 两者）、C-2b（越表元素的拒绝粒度）；另有 5 处旧口径 sidenote 的去留待定（`scripts/chembox.py` 的 IUPAC 提示、`references/deferrals.md` D-2 影响行、`STATUS.md` 的 A-2/A-3 与页码偏移条目、`textbook/MANIFEST.md` 的快照约定、`data/elements.jsonl` 的「图中值…」与 oracle 列）。

库级待决（不属于本技能）：技能仓库结构迁移提案 S-1..S-7（单仓 / 每技能状态目录 / 混合 / 全部子模块）；S-1（先做状态分仓）已执行，S-4/S-5/S-6 采用建议默认值，S-2/S-3/S-7 未决 —— 记录在父级 `.agent/state/pending-clarifications.md`。

**证据时效提示**：`/tmp` 已于 2026-09-16 被清空，早前存于 `/tmp` 的会话中间产物（`zll_elements_preview.jsonl`、`zll_elements_before_removal.jsonl`、渲染与解包目录）**已不存在**；上一轮会话登记的 `/tmp/yunxia-backups/*` 同样已消失。移除前的元素表内容可由当前文件**逐条重新追加**被移除的固定子句「；图中印刷值由照片转写，待 PDF 复核」重建，该子句原文记录在 `zlinglong/.agent/state/verification.md` 的 2026-09-16 条目中。
