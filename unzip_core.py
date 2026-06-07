from __future__ import annotations

import json
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Sequence

try:
    import py7zr  # type: ignore
except ImportError:  # pragma: no cover - optional runtime dependency
    py7zr = None

try:
    import rarfile  # type: ignore
except ImportError:  # pragma: no cover - optional runtime dependency
    rarfile = None

CONFIG_FILE_NAME = "unzip_config.json"
LOG_PREFIX = "unzip_log_"
SUPPORTED_ARCHIVES = {".zip", ".rar", ".7z"}
ZIP_PASSWORD_ENCODINGS = ["utf-8", "gbk", "gb2312", "latin1", "cp437"]


class MissingDependencyError(RuntimeError):
    pass


@dataclass
class ProgressUpdate:
    current: int
    total: int
    archive_name: str
    detail: str

    @property
    def fraction(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(max(self.current / self.total, 0.0), 1.0)


def normalize_passwords(password_entries: Iterable[str]) -> list[str]:
    passwords: list[str] = []
    for entry in password_entries:
        if entry is None:
            continue
        if entry.strip() == "":
            continue
        passwords.append(entry)
    return passwords or [""]


def mask_password(password: str) -> str:
    if not password:
        return "无密码"
    if len(password) <= 3:
        return "*" * len(password)
    return f"{password[:3]}***"


def load_passwords(config_path: Path) -> list[str]:
    if not config_path.exists():
        return []
    with config_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return [str(password) for password in payload.get("passwords", [])]


def save_passwords(config_path: Path, passwords: Sequence[str]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as file:
        json.dump({"passwords": list(passwords)}, file, ensure_ascii=False, indent=2)


def is_supported_archive(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_ARCHIVES


def find_archives(folder: Path | str) -> list[Path]:
    folder_path = Path(folder)
    archives: list[Path] = []

    for root, _, files in os.walk(folder_path):
        for file_name in files:
            file_path = Path(root) / file_name
            lower_name = file_name.lower()
            ext = file_path.suffix.lower()

            if ext == ".zip":
                archives.append(file_path)
            elif ext == ".rar":
                if ".part" not in lower_name or ".part1.rar" in lower_name or lower_name.endswith(".rar"):
                    if not lower_name.endswith(tuple(f".r{i:02d}" for i in range(100))):
                        if ".part" not in lower_name or ".part1.rar" in lower_name or lower_name.count(".part") == 0:
                            archives.append(file_path)
            elif ext == ".7z":
                if not lower_name.endswith(tuple(f".{i:03d}" for i in range(2, 1000))):
                    archives.append(file_path)

    return sorted(set(archives))


def write_log_file(folder: Path | str, log_messages: Sequence[str]) -> Path:
    folder_path = Path(folder)
    log_file = folder_path / f"{LOG_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with log_file.open("w", encoding="utf-8") as file:
        file.write("批量解压工具 - 操作日志\n")
        file.write("=" * 70 + "\n")
        file.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        file.write(f"文件夹: {folder_path}\n")
        file.write("=" * 70 + "\n\n")
        for message in log_messages:
            file.write(message + "\n")
    return log_file


def delete_archive_and_parts(archive_path: Path) -> list[Path]:
    deleted_files: list[Path] = []

    def delete_if_exists(path: Path) -> None:
        if path.exists():
            path.unlink()
            deleted_files.append(path)

    delete_if_exists(archive_path)

    base_name = archive_path.stem
    parent = archive_path.parent
    ext = archive_path.suffix.lower()

    if ext == ".zip":
        for index in range(1, 100):
            delete_if_exists(parent / f"{base_name}.z{index:02d}")
    elif ext == ".rar":
        for index in range(100):
            delete_if_exists(parent / f"{base_name}.r{index:02d}")
        if ".part1" in base_name:
            for index in range(2, 100):
                delete_if_exists(parent / f"{base_name.replace('.part1', f'.part{index}')}.rar")
        else:
            for index in range(2, 100):
                delete_if_exists(parent / f"{base_name}.part{index}.rar")
    elif ext == ".7z":
        for index in range(1, 1000):
            delete_if_exists(parent / f"{archive_path.name}.{index:03d}")

    return deleted_files


def resolve_7z_executable() -> str:
    env_override = os.environ.get("UNZIPTOOL_7Z_PATH", "").strip()
    if env_override and Path(env_override).exists():
        return env_override

    candidates = [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        "/mnt/c/Program Files/7-Zip/7z.exe",
        "/mnt/c/Program Files (x86)/7-Zip/7z.exe",
        shutil.which("7z.exe"),
        shutil.which("7z"),
        shutil.which("7za.exe"),
        shutil.which("7za"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise MissingDependencyError(
        "未找到 7-Zip。请先安装 7-Zip，或把 7z.exe 路径写入环境变量 UNZIPTOOL_7Z_PATH 后重试"
    )


class ArchiveExtractor:
    def __init__(self, log_callback: Callable[[str], None] | None = None):
        self.log_callback = log_callback or (lambda message: None)

    def log(self, message: str) -> None:
        self.log_callback(message)

    def extract_archive(
        self,
        archive_path: Path,
        passwords: Sequence[str],
        detail_callback: Callable[[str], None] | None = None,
    ) -> dict:
        result = {"success": False, "message": "", "skipped": False}
        ext = archive_path.suffix.lower()
        extract_path = archive_path.parent
        last_error: str | None = None
        use_7z_fallback = False
        seven_zip_password_fallback = False
        has_non_ascii_password = any(any(ord(char) > 127 for char in password) for password in passwords if password)

        if ext == ".zip" and has_non_ascii_password:
            seven_zip_password_fallback = True

        for index, password in enumerate(passwords, start=1):
            password_label = f"密码{index}: {mask_password(password)}"
            self.log(f"  尝试 {password_label}")
            try:
                if ext == ".zip":
                    if seven_zip_password_fallback:
                        self.log("  检测到 ZIP 使用非 ASCII 密码，直接走 7-Zip 兼容模式")
                        break
                    success = self._extract_zip(archive_path, extract_path, password, detail_callback)
                elif ext == ".rar":
                    success = self._extract_rar(archive_path, extract_path, password, detail_callback)
                elif ext == ".7z":
                    success = self._extract_7z(archive_path, extract_path, password, detail_callback)
                else:
                    result["skipped"] = True
                    result["message"] = f"不支持的格式: {ext}"
                    return result

                if success:
                    result["success"] = True
                    result["message"] = f"解压成功（{password_label}）" if password else "解压成功"
                    return result
            except Exception as error:  # noqa: BLE001
                last_error = str(error)
                self.log(f"  失败: {last_error}")
                if ext == ".zip":
                    lowered_error = last_error.lower()
                    if "span multiple disks" in last_error or "multi-disk" in lowered_error:
                        use_7z_fallback = True
                        break
                    if password and any(keyword in lowered_error for keyword in ["bad password", "wrong password", "password", "口令", "密码"]):
                        seven_zip_password_fallback = True
                        break

        if use_7z_fallback or seven_zip_password_fallback:
            try:
                seven_zip_path = resolve_7z_executable()
            except MissingDependencyError as error:
                result["message"] = str(error)
                return result

            fallback_reason = "分卷 ZIP" if use_7z_fallback else "ZIP 密码兼容性"
            self.log(f"  切换到 7-Zip 兼容模式：{fallback_reason}")

            for index, password in enumerate(passwords, start=1):
                password_label = f"密码{index}: {mask_password(password)}"
                self.log(f"  使用 7-Zip 再试一次：{password_label}")
                try:
                    if self._extract_with_7z(archive_path, extract_path, password, detail_callback, seven_zip_path=seven_zip_path):
                        result["success"] = True
                        result["message"] = f"使用 7-Zip 解压成功（{password_label}）"
                        return result
                except Exception as error:  # noqa: BLE001
                    last_error = str(error)
                    self.log(f"  失败: {last_error}")

        result["message"] = "所有密码都无法解压" if not last_error else f"所有密码都无法解压（最后错误: {last_error}）"
        return result

    def _extract_zip(
        self,
        archive_path: Path,
        extract_path: Path,
        password: str,
        detail_callback: Callable[[str], None] | None = None,
    ) -> bool:
        callback = detail_callback or (lambda detail: None)
        if not password:
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                names = zip_ref.namelist()
                total = max(len(names), 1)
                for index, name in enumerate(names, start=1):
                    zip_ref.extract(name, extract_path)
                    callback(f"ZIP {index}/{total}: {name}")
            return True

        last_error: Exception | None = None
        password_runtime_error: RuntimeError | None = None
        for encoding in ZIP_PASSWORD_ENCODINGS:
            try:
                encoded_password = password.encode(encoding)
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    names = zip_ref.namelist()
                    total = max(len(names), 1)
                    for index, name in enumerate(names, start=1):
                        zip_ref.extract(name, extract_path, pwd=encoded_password)
                        callback(f"ZIP {index}/{total}: {name}")
                return True
            except UnicodeEncodeError as error:
                last_error = error
            except RuntimeError as error:
                last_error = error
                if "password" in str(error).lower() or "密码" in str(error):
                    password_runtime_error = error
            except zipfile.BadZipFile as error:
                last_error = error
        if password_runtime_error:
            raise password_runtime_error
        if last_error:
            raise last_error
        return False

    def _extract_rar(
        self,
        archive_path: Path,
        extract_path: Path,
        password: str,
        detail_callback: Callable[[str], None] | None = None,
    ) -> bool:
        if rarfile is None:
            raise MissingDependencyError("缺少 rarfile 依赖，请先安装 requirements.txt")
        callback = detail_callback or (lambda detail: None)
        with rarfile.RarFile(archive_path, "r") as rar_ref:
            if password:
                rar_ref.setpassword(password)
            names = rar_ref.namelist()
            total = max(len(names), 1)
            for index, name in enumerate(names, start=1):
                rar_ref.extract(name, extract_path)
                callback(f"RAR {index}/{total}: {name}")
        return True

    def _extract_7z(
        self,
        archive_path: Path,
        extract_path: Path,
        password: str,
        detail_callback: Callable[[str], None] | None = None,
    ) -> bool:
        if py7zr is None:
            raise MissingDependencyError("缺少 py7zr 依赖，请先安装 requirements.txt")
        callback = detail_callback or (lambda detail: None)
        with py7zr.SevenZipFile(archive_path, "r", password=password or None) as archive:
            names = archive.getnames()
            callback(f"7Z 准备解压 {len(names)} 个文件")
            archive.extractall(extract_path)
            callback("7Z 100% 完成")
        return True

    def _extract_with_7z(
        self,
        archive_path: Path,
        extract_path: Path,
        password: str,
        detail_callback: Callable[[str], None] | None = None,
        seven_zip_path: str | None = None,
    ) -> bool:
        callback = detail_callback or (lambda detail: None)
        seven_zip = seven_zip_path or resolve_7z_executable()
        command = [seven_zip, "x", str(archive_path), f"-o{extract_path}", "-y"]
        command.append(f"-p{password}" if password else "-p")
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "7-Zip 返回未知错误")
        callback("7-Zip 外部解压完成")
        return True
