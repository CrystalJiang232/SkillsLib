# 教材 PDF 清单（骨架，未核验）

> 状态：**待解包**。五个容器已由用户提供，但均为 ZipCrypto 加密 zip，尚无可用密码；解包后把 PDF 放入本目录并按「册次」重命名。

## 待迁入文件（容器元数据，已核验）

| 容器 | 字节数 | sha256 | 内含条目 | 目标文件名 |
|------|--------|--------|----------|------------|
| `~/ref/1.edupdf` | 12666332 | `2f11e5c0e4c1b148c07cc2ea051c5a027a4ad4876fb8065ef55897bb100983dd` | `document.pdf` 14050385 B | 待识别后命名 |
| `~/ref/2.edupdf` | 11388744 | `09fa781d4c98e12b0a760b775b804ce5984c31ceac325a25245b31f53e4277cd` | `document.pdf` 12793174 B | 待识别后命名 |
| `~/ref/3.edupdf` | 10828969 | `cf810e322b718fbb26a14d1d060e4cc1b9597b099814b21ed3d1e14c7fc28c6f` | `document.pdf` 12241298 B | 待识别后命名 |
| `~/ref/4.edupdf` | 16590851 | `ae48d64eeb87b91eba0a3fa4ae05b1d3b611de2337056ee89da92ef427c44b67` | `document.pdf` 18413188 B | 待识别后命名 |
| `~/ref/5.edupdf` | 19888533 | `d498c52d0f3919583acc766af82eac0f6b2b3954d3f563e6b5763ff80d443cac` | `document.pdf` 22093382 B | 待识别后命名 |

## 命名约定（待识别后执行）

- 目标名：`必修第一册.pdf`、`必修第二册.pdf`、`选择性必修1-化学反应原理.pdf`、`选择性必修2-物质结构与性质.pdf`、`选择性必修3-有机化学基础.pdf`。
- 识别方法：渲染每册第 1 页为 PNG 后目视确认册次与版本，再按上表改名；容器编号与册次的对应关系以目视结果为准，不凭体积猜测。

## 风险

- R11：五册 PDF 合计约 76 MB，会使 `bin/zlinglong.skill` 体积显著增大（`package_skill.py` 打包整个目录）。
- R3：教材 PDF 的版权与分发范围需在打包前确认。

## 附录快照约定（解包后执行，用于数据导入的证据留存）

- 目录：`zlinglong/textbook/snapshots/`。
- 命名：`<册次>-pdf<PDF页序>-p<印刷页码>-<主题>.png`，例如 `必修第一册-pdf101-p85-相对原子质量表.png`；印刷页码无法辨认时写 `pNA`。
- 分辨率：正文表格用 `-r200`，密集小字表格用 `-r300`。
- 命令模板：

```bash
gs -q -dNOPAUSE -dBATCH -sDEVICE=png16m -r200 \
   -dFirstPage=<PDF页序> -dLastPage=<PDF页序> \
   -sOutputFile=zlinglong/textbook/snapshots/<册次>-pdf<PDF页序>-p<印刷页码>-<主题>.png \
   document.pdf
```

- 文本复核（可选，有文本层时）：`gs -q -dNOPAUSE -dBATCH -sDEVICE=txtwrite -dFirstPage=<p> -dLastPage=<p> -sOutputFile=- document.pdf`
- 用途：快照是「写什么」的证据载体；数据条目写入时应能在快照与 `source` 页码之间建立对应关系。
