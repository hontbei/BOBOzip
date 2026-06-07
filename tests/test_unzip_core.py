import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import zipfile

from unzip_core import (
    ArchiveExtractor,
    MissingDependencyError,
    find_archives,
    mask_password,
    normalize_passwords,
    resolve_7z_executable,
)


class UnzipCoreTests(unittest.TestCase):
    def test_normalize_passwords_preserves_exact_text_and_order(self):
        self.assertEqual(
            normalize_passwords(["  alpha  ", "", " beta", "   ", "中文 密码  ", "gamma"]),
            ["  alpha  ", " beta", "中文 密码  ", "gamma"],
        )

    def test_normalize_passwords_returns_empty_password_when_no_valid_entries(self):
        self.assertEqual(normalize_passwords(["", "   ", "\n"]), [""])

    def test_mask_password_hides_tail_but_keeps_prefix(self):
        self.assertEqual(mask_password("secret"), "sec***")
        self.assertEqual(mask_password("ab"), "**")
        self.assertEqual(mask_password(""), "无密码")

    def test_find_archives_returns_only_main_archive_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            files = [
                "movie.zip",
                "movie.z01",
                "movie.z02",
                "series.part1.rar",
                "series.part2.rar",
                "classic.rar",
                "classic.r00",
                "pack.7z",
                "pack.7z.001",
                "pack.7z.002",
                "notes.txt",
            ]
            for name in files:
                (tmp_path / name).write_text("demo", encoding="utf-8")

            found = [path.name for path in find_archives(tmp_path)]

            self.assertEqual(found, ["classic.rar", "movie.zip", "pack.7z", "series.part1.rar"])

    def test_resolve_7z_executable_prefers_explicit_env_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_7z = Path(tmp_dir) / "7z.exe"
            fake_7z.write_text("stub", encoding="utf-8")
            with mock.patch.dict(os.environ, {"UNZIPTOOL_7Z_PATH": str(fake_7z)}, clear=False):
                self.assertEqual(resolve_7z_executable(), str(fake_7z))

    def test_resolve_7z_executable_reports_clear_install_hint_when_missing(self):
        original_exists = Path.exists

        def fake_exists(path_obj: Path) -> bool:
            path_text = str(path_obj)
            if "7z" in path_text.lower():
                return False
            return original_exists(path_obj)

        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch("unzip_core.shutil.which", return_value=None), \
             mock.patch("pathlib.Path.exists", new=fake_exists):
            with self.assertRaises(MissingDependencyError) as context:
                resolve_7z_executable()

        self.assertIn("7-Zip", str(context.exception))
        self.assertIn("UNZIPTOOL_7Z_PATH", str(context.exception))

    def test_extract_archive_reports_missing_7z_once_for_multivolume_zip(self):
        extractor = ArchiveExtractor()
        messages = []

        with mock.patch.object(extractor, "_extract_zip", side_effect=RuntimeError("zipfiles that span multiple disks are not supported")), \
             mock.patch("unzip_core.resolve_7z_executable", side_effect=MissingDependencyError("未找到 7-Zip。请先安装 7-Zip，或把 7z.exe 路径写入环境变量 UNZIPTOOL_7Z_PATH 后重试")), \
             mock.patch.object(extractor, "_extract_with_7z") as extract_with_7z:
            result = extractor.extract_archive(Path("demo.zip"), ["pw1", "pw2", "pw3"], detail_callback=messages.append)

        extract_with_7z.assert_not_called()
        self.assertFalse(result["success"])
        self.assertIn("未找到 7-Zip", result["message"])
        self.assertIn("安装", result["message"])

    def test_extract_archive_prefers_7z_for_non_ascii_zip_passwords(self):
        extractor = ArchiveExtractor()

        with mock.patch("unzip_core.resolve_7z_executable", return_value="C:/Program Files/7-Zip/7z.exe"), \
             mock.patch.object(extractor, "_extract_with_7z", return_value=True) as extract_with_7z, \
             mock.patch.object(extractor, "_extract_zip") as extract_zip:
            result = extractor.extract_archive(Path("cn.zip"), ["Q群953442877"])

        extract_with_7z.assert_called_once()
        extract_zip.assert_not_called()
        self.assertTrue(result["success"])
        self.assertIn("7-Zip", result["message"])

    def test_extract_archive_falls_back_to_7z_when_zip_runtime_password_attempts_fail(self):
        extractor = ArchiveExtractor()

        with mock.patch.object(extractor, "_extract_zip", side_effect=RuntimeError("Bad password for file")), \
             mock.patch("unzip_core.resolve_7z_executable", return_value="C:/Program Files/7-Zip/7z.exe"), \
             mock.patch.object(extractor, "_extract_with_7z", return_value=True) as extract_with_7z:
            result = extractor.extract_archive(Path("cn.zip"), [" 中文密码 "])

        extract_with_7z.assert_called_once()
        called_password = extract_with_7z.call_args.args[2]
        self.assertEqual(called_password, " 中文密码 ")
        self.assertTrue(result["success"])
        self.assertIn("7-Zip", result["message"])

    def test_extract_zip_retries_with_7z_for_unicode_password_runtime_errors(self):
        extractor = ArchiveExtractor()
        unicode_password = "中文密码"

        with mock.patch("zipfile.ZipFile") as zip_file_cls, \
             mock.patch("unzip_core.resolve_7z_executable", return_value="C:/Program Files/7-Zip/7z.exe"), \
             mock.patch.object(extractor, "_extract_with_7z", return_value=True) as extract_with_7z:
            zip_instance = zip_file_cls.return_value.__enter__.return_value
            zip_instance.namelist.return_value = ["demo.txt"]
            zip_instance.extract.side_effect = RuntimeError("Bad password for file")

            result = extractor.extract_archive(Path("demo.zip"), [unicode_password])

        extract_with_7z.assert_called_once()
        self.assertTrue(result["success"])
        self.assertIn("7-Zip", result["message"])


if __name__ == "__main__":
    unittest.main()
