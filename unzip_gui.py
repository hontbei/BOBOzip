import threading
from datetime import datetime
from pathlib import Path
import tkinter.messagebox as messagebox
from tkinter import filedialog

import customtkinter as ctk

from unzip_core import (
    ArchiveExtractor,
    MissingDependencyError,
    delete_archive_and_parts,
    find_archives,
    get_config_path,
    load_passwords,
    normalize_passwords,
    open_in_file_manager,
    resolve_7z_executable,
    save_passwords,
    write_log_file,
)


APP_TITLE = "UnzipTool"
WINDOW_SIZE = "1120x760"
DEFAULT_APPEARANCE = "dark"
DEFAULT_THEME = "blue"
CONFIG_FILE = get_config_path()


class UnzipToolApp:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.minsize(1040, 720)

        ctk.set_appearance_mode(DEFAULT_APPEARANCE)
        ctk.set_default_color_theme(DEFAULT_THEME)

        self.folder_path = ctk.StringVar()
        self.progress_text = ctk.StringVar(value="准备就绪，等你点开始。")
        self.detail_text = ctk.StringVar(value="还没开始扫描。")
        self.status_hint_text = ctk.StringVar(value="7-Zip 检测：未检查")
        self.stats_text = ctk.StringVar(value="成功 0 / 失败 0 / 跳过 0")
        self.password_count_text = ctk.StringVar(value="密码库：0 项")
        self.archive_count_text = ctk.StringVar(value="待处理压缩包：0")

        self.password_cards: list[str] = []
        self.log_messages: list[str] = []
        self.is_processing = False
        self.stop_requested = False
        self.extractor = ArchiveExtractor(log_callback=self.log)

        self._build_layout()
        self._load_config()
        self.refresh_password_cards()
        self.check_7z_status()

    def _build_layout(self) -> None:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        container = ctk.CTkFrame(self.root, corner_radius=18)
        container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        container.grid_columnconfigure(0, weight=3)
        container.grid_columnconfigure(1, weight=2)
        container.grid_rowconfigure(0, weight=1)

        self._build_left_panel(container)
        self._build_right_panel(container)

    def _build_left_panel(self, parent: ctk.CTkFrame) -> None:
        left_panel = ctk.CTkFrame(parent, corner_radius=16)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=0)
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(3, weight=1)

        header = ctk.CTkFrame(left_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="批量解压工具",
            font=ctk.CTkFont(size=28, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="CustomTkinter 重做界面，别再像上世纪控件拼盘。",
            text_color=("gray40", "gray70"),
            font=ctk.CTkFont(size=14),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        folder_card = ctk.CTkFrame(left_panel, corner_radius=16)
        folder_card.grid(row=1, column=0, sticky="ew", padx=18, pady=8)
        folder_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(folder_card, text="目标文件夹", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 8)
        )
        ctk.CTkEntry(
            folder_card,
            textvariable=self.folder_path,
            height=42,
            placeholder_text="选择包含压缩包的文件夹",
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))

        folder_actions = ctk.CTkFrame(folder_card, fg_color="transparent")
        folder_actions.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))
        folder_actions.grid_columnconfigure(0, weight=1)
        folder_actions.grid_columnconfigure(1, weight=1)
        folder_actions.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(folder_actions, text="浏览文件夹", command=self.browse_folder, height=40).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ctk.CTkButton(folder_actions, text="扫描压缩包", command=self.scan_archives, height=40).grid(
            row=0, column=1, sticky="ew", padx=4
        )
        ctk.CTkButton(folder_actions, text="打开目录", command=self.open_folder, height=40).grid(
            row=0, column=2, sticky="ew", padx=(8, 0)
        )

        progress_card = ctk.CTkFrame(left_panel, corner_radius=16)
        progress_card.grid(row=2, column=0, sticky="ew", padx=18, pady=8)
        progress_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(progress_card, text="进度面板", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 8)
        )
        ctk.CTkLabel(progress_card, textvariable=self.progress_text, font=ctk.CTkFont(size=15)).grid(
            row=1, column=0, sticky="w", padx=16
        )
        ctk.CTkLabel(
            progress_card,
            textvariable=self.detail_text,
            text_color=("gray35", "gray75"),
            wraplength=600,
            justify="left",
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(6, 8))
        ctk.CTkLabel(
            progress_card,
            textvariable=self.status_hint_text,
            text_color=("#D4A017", "#F0C05A"),
            wraplength=600,
            justify="left",
        ).grid(row=3, column=0, sticky="w", padx=16, pady=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(progress_card, height=18, corner_radius=10)
        self.progress_bar.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.progress_bar.set(0)

        stat_row = ctk.CTkFrame(progress_card, fg_color="transparent")
        stat_row.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 14))
        stat_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(stat_row, textvariable=self.archive_count_text).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(stat_row, textvariable=self.stats_text).grid(row=0, column=1, sticky="e")

        log_card = ctk.CTkFrame(left_panel, corner_radius=16)
        log_card.grid(row=3, column=0, sticky="nsew", padx=18, pady=(8, 18))
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)

        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        log_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(log_header, text="操作日志", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkButton(log_header, text="清空日志", width=92, command=self.clear_log).grid(row=0, column=1, sticky="e")

        self.log_textbox = ctk.CTkTextbox(log_card, corner_radius=12)
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.log_textbox.configure(state="disabled")

    def _build_right_panel(self, parent: ctk.CTkFrame) -> None:
        right_panel = ctk.CTkFrame(parent, corner_radius=16)
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(2, weight=1)

        control_card = ctk.CTkFrame(right_panel, corner_radius=16)
        control_card.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        control_card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(control_card, text="操作", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 10), columnspan=2
        )

        self.start_button = ctk.CTkButton(
            control_card,
            text="开始解压",
            height=46,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.start_unzip,
        )
        self.start_button.grid(row=1, column=0, sticky="ew", padx=(16, 8), pady=(0, 16))

        self.stop_button = ctk.CTkButton(
            control_card,
            text="停止",
            height=46,
            fg_color="#B33939",
            hover_color="#912C2C",
            command=self.stop_unzip,
            state="disabled",
        )
        self.stop_button.grid(row=1, column=1, sticky="ew", padx=(8, 16), pady=(0, 16))

        password_input_card = ctk.CTkFrame(right_panel, corner_radius=16)
        password_input_card.grid(row=1, column=0, sticky="ew", padx=18, pady=10)
        password_input_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(password_input_card, text="密码库", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 4)
        )
        ctk.CTkLabel(
            password_input_card,
            textvariable=self.password_count_text,
            text_color=("gray35", "gray75"),
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        self.password_entry = ctk.CTkEntry(password_input_card, height=42, placeholder_text="输入一个密码后点添加")
        self.password_entry.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.password_entry.bind("<Return>", lambda _event: self.add_password())

        password_actions = ctk.CTkFrame(password_input_card, fg_color="transparent")
        password_actions.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 14))
        password_actions.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkButton(password_actions, text="添加密码", command=self.add_password).grid(
            row=0, column=0, sticky="ew", padx=(0, 6)
        )
        ctk.CTkButton(password_actions, text="批量导入", command=self.import_passwords_dialog).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ctk.CTkButton(password_actions, text="清空密码", command=self.clear_passwords, fg_color="#444", hover_color="#555").grid(
            row=0, column=2, sticky="ew", padx=(6, 0)
        )

        password_list_card = ctk.CTkFrame(right_panel, corner_radius=16)
        password_list_card.grid(row=2, column=0, sticky="nsew", padx=18, pady=(10, 18))
        password_list_card.grid_columnconfigure(0, weight=1)
        password_list_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(password_list_card, text="密码块列表", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 10)
        )
        self.password_scroll = ctk.CTkScrollableFrame(password_list_card, corner_radius=12)
        self.password_scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.password_scroll.grid_columnconfigure(0, weight=1)

    def run_on_ui(self, callback, *args, **kwargs) -> None:
        self.root.after(0, lambda: callback(*args, **kwargs))

    def check_7z_status(self) -> None:
        try:
            seven_zip_path = resolve_7z_executable()
            self.status_hint_text.set(f"7-Zip 检测：已找到 -> {seven_zip_path}")
        except MissingDependencyError as error:
            self.status_hint_text.set(f"7-Zip 检测：{error}")

    def _load_config(self) -> None:
        try:
            stored_passwords = load_passwords(CONFIG_FILE)
            self.password_cards = normalize_passwords(stored_passwords) if stored_passwords else []
        except Exception as error:  # noqa: BLE001
            self.password_cards = []
            self.log(f"加载配置失败：{error}")

    def save_config(self) -> None:
        save_passwords(CONFIG_FILE, self.password_cards)

    def browse_folder(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path.set(folder)
            self.scan_archives(log_result=False)

    def open_folder(self) -> None:
        folder = self.folder_path.get().strip()
        if not folder:
            messagebox.showwarning("提示", "先选文件夹，别拿空气当目录。")
            return
        if not Path(folder).exists():
            messagebox.showerror("错误", "目录不存在，你这路径比没睡醒还虚。")
            return
        open_in_file_manager(folder)

    def import_passwords_dialog(self) -> None:
        dialog = ctk.CTkInputDialog(
            text="每行一个密码，也支持逗号分隔。",
            title="批量导入密码",
        )
        result = dialog.get_input()
        if not result:
            return
        raw_items = []
        for line in result.replace("，", ",").splitlines():
            parts = line.split(",") if "," in line else [line]
            raw_items.extend(part for part in parts if part.strip())
        new_passwords = raw_items
        self.merge_passwords(new_passwords)

    def merge_passwords(self, passwords: list[str]) -> None:
        changed = False
        for password in passwords:
            if password and password not in self.password_cards:
                self.password_cards.append(password)
                changed = True
        if changed:
            self.password_cards.sort(key=str.lower)
            self.refresh_password_cards()
            self.save_config()
            self.log(f"已导入 {len(passwords)} 条密码")

    def add_password(self) -> None:
        password = self.password_entry.get()
        if password.strip() == "":
            messagebox.showwarning("提示", "密码框都空着，你添加个寂寞。")
            return
        if password in self.password_cards:
            messagebox.showinfo("提示", "这个密码已经在列表里了，别复读。")
            return
        self.password_cards.append(password)
        self.password_cards.sort(key=str.lower)
        self.password_entry.delete(0, "end")
        self.refresh_password_cards()
        self.save_config()
        self.log(f"新增密码：{password[:3]}***")

    def clear_passwords(self) -> None:
        self.password_cards = []
        self.refresh_password_cards()
        self.save_config()
        self.log("已清空密码库")

    def remove_password(self, password: str) -> None:
        self.password_cards = [item for item in self.password_cards if item != password]
        self.refresh_password_cards()
        self.save_config()
        self.log(f"已移除密码：{password[:3]}***")

    def refresh_password_cards(self) -> None:
        for child in self.password_scroll.winfo_children():
            child.destroy()

        if not self.password_cards:
            placeholder = ctk.CTkLabel(
                self.password_scroll,
                text="还没有密码。现在这块空得像你没整理过的下载目录。",
                text_color=("gray45", "gray70"),
                wraplength=320,
                justify="left",
            )
            placeholder.grid(row=0, column=0, sticky="w", padx=6, pady=6)
        else:
            for index, password in enumerate(self.password_cards):
                card = ctk.CTkFrame(self.password_scroll, corner_radius=14)
                card.grid(row=index, column=0, sticky="ew", padx=4, pady=6)
                card.grid_columnconfigure(0, weight=1)

                ctk.CTkLabel(
                    card,
                    text=f"#{index + 1}",
                    width=42,
                    height=34,
                    corner_radius=10,
                    fg_color=("gray80", "gray20"),
                ).grid(row=0, column=0, sticky="w", padx=(12, 10), pady=12)

                text_wrap = ctk.CTkFrame(card, fg_color="transparent")
                text_wrap.grid(row=0, column=1, sticky="ew", pady=12)
                text_wrap.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(text_wrap, text=password, anchor="w", font=ctk.CTkFont(size=15, weight="bold")).grid(
                    row=0, column=0, sticky="w"
                )
                ctk.CTkLabel(
                    text_wrap,
                    text=f"预览：{password[:3]}***    长度：{len(password)}",
                    text_color=("gray35", "gray75"),
                    anchor="w",
                ).grid(row=1, column=0, sticky="w", pady=(4, 0))

                ctk.CTkButton(
                    card,
                    text="删除",
                    width=72,
                    fg_color="#B33939",
                    hover_color="#912C2C",
                    command=lambda current=password: self.remove_password(current),
                ).grid(row=0, column=2, sticky="e", padx=(10, 12), pady=12)

        self.password_count_text.set(f"密码库：{len(self.password_cards)} 项")

    def clear_log(self) -> None:
        self.log_messages = []
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self.log_messages.append(formatted)
        self.run_on_ui(self._append_log, formatted)

    def _append_log(self, message: str) -> None:
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def scan_archives(self, log_result: bool = True) -> None:
        folder = self.folder_path.get().strip()
        if not folder:
            self.archive_count_text.set("待处理压缩包：0")
            return
        folder_path = Path(folder)
        if not folder_path.exists():
            self.archive_count_text.set("待处理压缩包：0")
            if log_result:
                messagebox.showerror("错误", "目录不存在")
            return
        archives = find_archives(folder_path)
        self.archive_count_text.set(f"待处理压缩包：{len(archives)}")
        if log_result:
            self.log(f"扫描完成：找到 {len(archives)} 个压缩包")

    def start_unzip(self) -> None:
        folder = self.folder_path.get().strip()
        if not folder:
            messagebox.showwarning("提示", "请选择目标文件夹")
            return
        folder_path = Path(folder)
        if not folder_path.exists():
            messagebox.showerror("错误", "目标文件夹不存在")
            return
        if self.is_processing:
            return

        self.save_config()
        self.is_processing = True
        self.stop_requested = False
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.progress_bar.set(0)
        self.progress_text.set("开始扫描压缩包...")
        self.detail_text.set("准备线程任务中")
        self.status_hint_text.set("7-Zip 检测中...")
        self.stats_text.set("成功 0 / 失败 0 / 跳过 0")

        worker = threading.Thread(target=self.process_folder, args=(folder_path,), daemon=True)
        worker.start()

    def stop_unzip(self) -> None:
        self.stop_requested = True
        self.log("收到停止请求，当前文件处理完就会停。")
        self.detail_text.set("正在尝试安全停止...")

    def process_folder(self, folder: Path) -> None:
        success_count = 0
        fail_count = 0
        skip_count = 0

        try:
            self.log(f"开始扫描文件夹：{folder}")
            archives = find_archives(folder)
            self.run_on_ui(self.archive_count_text.set, f"待处理压缩包：{len(archives)}")

            if not archives:
                self.run_on_ui(self.progress_text.set, "一个压缩包都没找到。")
                self.run_on_ui(self.detail_text.set, "请检查目录，或者别对着空文件夹按开始。")
                self.run_on_ui(messagebox.showinfo, "提示", "没有找到可处理的压缩包")
                return

            passwords = normalize_passwords(self.password_cards)
            self.log(f"找到 {len(archives)} 个压缩包，准备使用 {len(passwords)} 个密码尝试")
            self.run_on_ui(self.check_7z_status)

            total = len(archives)
            for index, archive_path in enumerate(archives, start=1):
                if self.stop_requested:
                    self.log("操作已停止")
                    break

                self.run_on_ui(self.progress_text.set, f"处理中：{archive_path.name}  ({index}/{total})")
                self.run_on_ui(self.detail_text.set, "正在尝试解压...")
                self.run_on_ui(self.progress_bar.set, (index - 1) / total)

                result = self.extractor.extract_archive(
                    archive_path,
                    passwords,
                    detail_callback=lambda detail, current=index, total_count=total, name=archive_path.name: self.report_detail(
                        current,
                        total_count,
                        name,
                        detail,
                    ),
                )

                if result["success"]:
                    success_count += 1
                    self.log(f"✓ 成功：{archive_path.name}")
                    deleted_files = delete_archive_and_parts(archive_path)
                    if deleted_files:
                        self.log("  已删除：" + ", ".join(path.name for path in deleted_files))
                elif result["skipped"]:
                    skip_count += 1
                    self.log(f"○ 跳过：{archive_path.name} - {result['message']}")
                else:
                    fail_count += 1
                    self.log(f"✗ 失败：{archive_path.name} - {result['message']}")

                self.run_on_ui(self.progress_bar.set, index / total)
                self.run_on_ui(self.stats_text.set, f"成功 {success_count} / 失败 {fail_count} / 跳过 {skip_count}")

            log_file = write_log_file(folder, self.log_messages)
            self.log(f"日志已保存：{log_file.name}")

            if self.stop_requested:
                self.run_on_ui(self.progress_text.set, "已停止")
                self.run_on_ui(self.detail_text.set, "用户中断，已保留当前结果。")
            else:
                self.run_on_ui(self.progress_text.set, "处理完成")
                self.run_on_ui(self.detail_text.set, "活干完了，这次界面总算没那么土。")
                self.run_on_ui(
                    messagebox.showinfo,
                    "完成",
                    f"解压完成\n成功：{success_count}\n失败：{fail_count}\n跳过：{skip_count}",
                )
        except Exception as error:  # noqa: BLE001
            self.log(f"发生错误：{error}")
            self.run_on_ui(self.progress_text.set, "处理失败")
            self.run_on_ui(self.detail_text.set, str(error))
            self.run_on_ui(messagebox.showerror, "错误", f"发生错误：{error}")
        finally:
            self.run_on_ui(self.stats_text.set, f"成功 {success_count} / 失败 {fail_count} / 跳过 {skip_count}")
            self.run_on_ui(self.finish_processing)

    def report_detail(self, current: int, total: int, archive_name: str, detail: str) -> None:
        self.run_on_ui(self.detail_text.set, f"[{current}/{total}] {archive_name} -> {detail}")

    def finish_processing(self) -> None:
        self.is_processing = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        if self.stop_requested:
            self.progress_bar.set(0)
        else:
            self.progress_bar.set(1)


def main() -> None:
    root = ctk.CTk()
    UnzipToolApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
