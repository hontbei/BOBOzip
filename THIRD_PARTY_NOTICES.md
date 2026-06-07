# 第三方组件声明 (Third-Party Notices)

BOBOzip 使用了以下开源组件，各自遵循其原始许可证：

| 组件 | 许可证 | 用途 |
|------|--------|------|
| CustomTkinter | MIT License | 图形界面 |
| Pillow (PIL) | MIT-CMU / HPND | 图标与磁贴生成、界面图像 |
| py7zr | LGPL-2.1-or-later | 7Z 解压 |
| rarfile | ISC License | RAR 解压（封装外部 UnRAR） |

## 关于 RAR / UnRAR

`rarfile` 本身遵循 ISC 许可证，但解压 RAR 时会调用外部的 UnRAR 工具或 7-Zip。
UnRAR 的许可证允许自由使用其解压能力，但明确禁止将其源码用于重建 RAR 压缩
（compression）算法。BOBOzip 仅使用其解压（decompression）能力，符合该限制。

各许可证全文可在对应项目仓库获取：

- CustomTkinter: https://github.com/TomSchimansky/CustomTkinter
- Pillow: https://github.com/python-pillow/Pillow
- py7zr: https://github.com/miurahr/py7zr
- rarfile: https://github.com/markokr/rarfile
- UnRAR license: https://www.rarlab.com/license.htm
