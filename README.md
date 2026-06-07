# BOBOzip (UnzipTool)

一个基于 CustomTkinter 的批量解压工具，支持 ZIP / RAR / 7Z，自动尝试密码、处理分卷，并在成功后清理压缩包。

## 功能特性

- 批量扫描并解压文件夹内的 ZIP / RAR / 7Z 压缩包
- 自动尝试密码库中的密码
- 现代化图形界面，密码以卡片形式展示
- 可视化进度条、当前处理状态与统计信息
- 支持单个添加、批量导入、删除密码，并自动保存密码库
- 成功解压后自动删除压缩包与分卷
- 自动写入解压日志

## 项目结构

- `unzip_gui.py`：图形界面入口
- `unzip_core.py`：解压、扫描、删除、日志等核心逻辑
- `unzip_config.json`：密码配置
- `requirements.txt`：依赖列表
- `tests/test_unzip_core.py`：核心逻辑测试

## 安装依赖

```bash
pip install -r requirements.txt
```

- 解压 RAR：Windows 需安装 UnRAR 或 WinRAR/UnRAR 可执行工具
- 处理某些分卷 ZIP：建议安装 7-Zip，并确保 `7z.exe` 可用

## 启动方式

双击 `启动UnzipTool.bat`，或命令行运行：

```bash
python unzip_gui.py
```

## 测试

```bash
python -m unittest tests/test_unzip_core.py
```

## 打包发布

支持构建 Windows 便携版（单文件 exe）、Windows MSIX 安装包，以及 Linux AppImage。
详见 [BUILD.md](BUILD.md)。

- Windows 便携版：`python -m PyInstaller bobozip.spec --clean --noconfirm`
- 推送 `v*` tag 会通过 GitHub Actions 自动构建并发布到 Release

## 提醒

1. 解压成功后**可选**删除压缩包（默认关闭），勾选后请先备份重要文件
2. 依赖未安装齐全时，RAR / 7Z 功能会报缺少依赖
3. 若未安装 7-Zip，分卷 ZIP 的兜底方案无法使用
4. 推荐在 Windows 下运行此 GUI

## 许可证

本软件为专有软件，保留所有权利，详见 [LICENSE](LICENSE)。
第三方开源组件声明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
