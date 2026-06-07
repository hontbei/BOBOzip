# 构建与打包说明

BOBOzip 支持以下发行版本：

| 平台 | 产物 | 说明 |
|------|------|------|
| Windows 便携版 | `BOBOzip-portable.exe` | 单文件，免安装，双击即用 |
| Windows MSIX | `BOBOzip.msix` | 现代安装/卸载，可上架商店（替代旧版 UWP 设想） |
| Linux | `BOBOzip-x86_64.AppImage` | 尽力支持，非主力目标 |

> macOS 暂未提供（无签名账号与测试设备）。
> "UWP" 在技术上无法直接由 Tkinter 程序生成，已用 MSIX 全自由度桌面包替代。

## 本地构建（Windows）

需要 Python 3.12+ 与依赖：

```bash
pip install -r requirements.txt
pip install pyinstaller
```

### 1. 便携版 exe

```bash
python -m PyInstaller bobozip.spec --clean --noconfirm
```

产物在 `dist/BOBOzip.exe`。

### 2. MSIX 包

需要安装 Windows SDK（提供 `makeappx.exe` / `signtool.exe`）。

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_msix.ps1
```

产物在 `dist/BOBOzip.msix`，同时生成自签名证书 `dist/BOBOzip-selfsigned.cer`。

安装 MSIX 前，需先把该证书导入到本机的“受信任人 (Trusted People)”：

```powershell
Import-Certificate -FilePath dist/BOBOzip-selfsigned.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople
```

然后双击 `BOBOzip.msix` 安装。

> 注：自签名证书仅用于本地/开源分发。若要上架微软商店或免证书安装，需要正式的代码签名证书。

### 上架微软商店

正式发布到微软商店请参见 [STORE_RELEASE.md](STORE_RELEASE.md)。
商店包用 `-Store` 参数生成（未签名，由商店重新签名）：

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_msix.ps1 -Store `
  -IdentityName "<Partner Center 的 Name>" `
  -Publisher "<Partner Center 的 Publisher>"
```

## 自动构建（GitHub Actions）

`.github/workflows/build.yml` 会在以下情况触发：

- 推送 `v*` 形式的 tag（如 `v1.0.0`）：构建全部平台并自动发布到 GitHub Release
- 手动触发（Actions 页面的 workflow_dispatch）：仅构建并上传产物

发布新版本：

```bash
git tag v1.0.0
git push origin v1.0.0
```

## 关于配置文件位置

- 从源码运行时：`unzip_config.json` 保存在程序目录
- 打包成 exe/MSIX 后：保存在用户目录
  - Windows: `%APPDATA%\BOBOzip\unzip_config.json`
  - Linux: `~/.config/BOBOzip/unzip_config.json`
  - macOS: `~/Library/Application Support/BOBOzip/unzip_config.json`
