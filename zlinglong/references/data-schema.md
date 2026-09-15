# data/*.jsonl 字段契约（骨架，未核验）

> 状态：骨架占位。字段已定，内容待教材迁移阶段写入（D-3）。

## 通用字段

| 字段 | 含义 | 约束 |
|------|------|------|
| `id` | 稳定条目句柄 | 前缀区分表：`el-`、`sol-`、`val-`、`eq-`、`k-`、`ser-`、`sub-` |
| `status` | 核验状态 | `unchecked` / `verified` |
| `source` | 来源 | 受控词表：`课标`、`教材:<册次>#<章节>`、`教材:<册次>#<章节>p<页>`、`官方解读`、`chemlib:<相对路径>`、`其他:<说明>` |
| `note` | 备注 | 可选 |

## 各表附加字段

| 文件 | 附加字段 |
|------|----------|
| `elements.jsonl` | `symbol`、`name_zh`、`mass_textbook`、`mass_mendeleev`、`mass_chemlib`、`preferred` |
| `solubility.jsonl` | `cation`、`anion`、`result`（溶/微溶/不溶/遇水分解） |
| `valences.jsonl` | `species`、`common_valences` |
| `equations.jsonl` | `reaction`、`conditions`、`type`、`chapter` |
| `constants.jsonl` | `name`、`value`、`temperature`、`units` |
| `series.jsonl` | `name`、`order`、`direction` |
| `substances.jsonl` | `formula`、`color`、`state`、`trivial_name`、`uses` |

## 占位约定

- 骨架阶段每个文件仅含一条 `{"id":"__placeholder__","status":"unchecked",...}` 记录。
- 该记录不得被检索结果引用为事实；命中占位即返回「知识库未收录」。
