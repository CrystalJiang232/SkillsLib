---
name: zlinglong
description: >
  醉玲珑（zlinglong）— 中国高中化学（人教版2019）知识与计算层。事实与数值只取自随包 data/ 数据文件与随包脚本
  （vendored chemlib + numpy/scipy/sympy），不联网、不引用模型记忆。提供四个模块：计算与结果核对、解题、过程分析、题目拓展，
  输出必附出处附录（file:line）。当前为骨架阶段，全部未完成内容标注「未核验 / unchecked」。
  Use when answering Chinese senior-high-school chemistry questions (必修第一册 through 选择性必修3) that need
  textbook-grounded facts or numeric verification. Do not use for 大学化学/竞赛超纲内容、旧教材(旧选修3/4/5)、
  备课与考点分析、讲法切换等教学法任务，或任何非中文输出需求。
metadata:
  status: skeleton-unchecked
  stage: 骨架（chevendored chemlib 已就位；教材迁移与 chemlib 调整推迟）
---

# 醉玲珑 · zlinglong

> **当前状态：骨架阶段（skeleton，未核验 / unchecked）。** 知识库与部分脚本仍是占位，凡标注「未核验」的内容在完成核验前不得作为最终依据输出。

## 0. 当前阶段与已推迟事项

- 已就位：`vendor/chemlib/`（chemlib 2.2.4 原样副本，MIT，未做任何修改）。
- 已推迟：离子/电荷相关计算与电化学（含离子方程式、电荷守恒、原电池与电解计算）——见 `references/deferrals.md` D-1。
- 已推迟：chemlib 值调整（教材相对原子质量、化合价列、公式重排、PIL 路径移除、包重命名）——见 D-2。
- 已推迟：教材 PDF 迁移（数据与原理条目的真正内容来源）——见 D-3。
- 未提供：数值核验集（Z-A 决定暂不提供），故全部计算模块默认带「未核验」标记——见 D-4。

## 1. 范围与触发

- 覆盖：人教版2019 必修第一册、必修第二册、选择性必修1《化学反应原理》、选择性必修2《物质结构与性质》、选择性必修3《有机化学基础》。
- 语言：仅中文作答，化学式与标准记号原样保留。
- 触发：高中化学问题，且需要教材依据或数值核对。
- 不触发：大学化学与竞赛超纲内容、旧教材及其映射、备课与考点分析、讲法切换、非中文输出。

## 2. 硬规则（must / never）

1. 事实与数值只能来自 `data/`、`knowledge/`、`vendor/chemlib/` 数据或 `scripts/` 的执行输出；模型记忆与联网检索一律禁止。
2. 数据文件缺少条目时，回答「知识库未收录」并给出最接近条目，不得猜测或补算。
3. 一切数值计算必须经由 `scripts/` 执行，且计算引擎为 `vendor/chemlib/`（后续扩展模块同源）；不得手写零依赖计算器。
4. 每次输出必须以出处附录结束，附录中的 `file:line` 必须来自工具输出（`rg -n` 或脚本），不得自行编造或推算。
5. 缺少依赖时按 `scripts/deps_check.py` 的 FATAL 模板停机并报告，不得降级为口算或记忆作答。
6. 不得安装任何包或改动系统环境；依赖由环境方提供。
7. 检索采用 grep-first：对 `knowledge/`、`data/` 用 `rg -n` 定位，条目以可 grep 的 id 记号标注。

## 3. 工作流（固定顺序）

1. 判定模块（计算与结果核对 / 解题 / 过程分析 / 题目拓展）。
2. 执行依赖自检：`python scripts/deps_check.py`。
3. 取事实：`rg -n "<关键词或条目 id>" knowledge/ data/`，记录命中的 `file:line`。
4. 取数值：`python scripts/chembox.py <子命令>`（详见 `references/module-contracts.md`）。
5. 组织中文答案，数值与单位、有效数字显式标注。
6. 输出出处附录（格式见 `references/provenance-appendix.md`）。

## 4. 四个模块的调用契约

四个模块的输入、必需调用、输出结构与失败形态统一记录在 `references/module-contracts.md`；本文件只保留路由与硬规则，避免双重来源。

## 5. 出处附录契约

- 附录必须列出本次回答实际使用的知识条目与脚本函数，格式为 `file:line` 加条目 id。
- 附录的坐标来自第 3 步的 `rg -n` 输出或脚本输出，原样复制。
- 未查询任何知识文件（正常不应发生）时，附录必须显式声明。
- 涉及被推迟能力（如离子/电荷）时，附录标注该结论为「推迟」而非「已计算」。

## 6. 错误行为

| 情形 | 行为 |
|------|------|
| 数据文件缺少条目 | 回答「知识库未收录」，附最接近条目与 `file:line` |
| 依赖缺失 | `deps_check` FATAL 模板 + 指向 `references/dependencies.md` |
| 超纲 / 旧教材 | 明确拒答并说明范围 |
| 命中推迟能力（离子/电荷、电化学） | 回答「知识库未收录（该能力推迟）」并引用 D-1 |
| 数据与教材取值冲突 | 以教材取值为准，附录并列显示冲突值与来源 |

## 7. 资源路由

- `references/deferrals.md`：推迟事项登记表（先读）。
- `references/dependencies.md`：运行时依赖与版本要求。
- `references/data-schema.md`：`data/*.jsonl` 字段契约。
- `references/provenance-appendix.md`：附录格式与失败分支。
- `references/module-contracts.md`：四模块 I/O 契约。
- `references/authoritative-sources.md`：权威来源层级与禁引来源。
- `knowledge/<册次>/`：各册原理条目（骨架占位）。
- `data/`：结构化事实（骨架占位）。
- `vendor/chemlib/`：随包计算引擎（原样副本）。

## 8. 未核验标记规范

- 占位或不完整的文件、条目、函数，均在首行或记录内标注「未核验 / unchecked」。
- 骨架阶段的默认值：所有 `data/*.jsonl` 记录曾为占位、所有 `knowledge/**` 条目均为占位、`scripts/extensions/**` 全部为未实现占位。
- 核验完成后，必须同时移除标记并在 `references/deferrals.md` 登记核验证据。
