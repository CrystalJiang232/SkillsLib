# 第三方组件声明（THIRD_PARTY_NOTICES）

| 组件 | 版本 | 位置 | 许可 | 处理方式 |
|------|------|------|------|----------|
| chemlib | 2.2.4 | `vendor/chemlib/` | MIT（原 `LICENSE.txt` 随副本保存） | 原样复制，未做修改；上游 https://github.com/harirakul/chemlib |

- 副本来源：`/home/hibiscus/miniforge3/lib/python3.12/site-packages/chemlib`（PyPI chemlib 2.2.4）。
- 复制时仅移除 `__pycache__`，源码与资源文件逐字节保持原样（sha256 见 `references/dependencies.md`）。
- 计划中的修改（教材相对原子质量、化合价列、公式重排、PIL 路径移除、包重命名）尚未执行，属推迟事项 D-2。
- 构建期参考库（ChePy BSD-2-Clause、mendeleev MIT）不随包分发，仅用于生成与核对数据。
