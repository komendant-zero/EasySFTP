"""
Диалоговое окно настройки прав доступа (chmod) на сервере.
Современный наглядный интерфейс с интерактивной матрицей, готовыми пресетами
и мгновенным расчётом восьмеричного и символьного форматов прав.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

from ui.theme import ThemeManager


class PermissionsDialog(tk.Toplevel):
    """
    Окно изменения прав доступа к файлу или папке на SFTP-сервере.
    """
    def __init__(
        self,
        parent: tk.Tk,
        filename: str,
        initial_mode: int,
        is_dir: bool,
        theme_mgr: ThemeManager,
        on_apply: Callable[[int, bool], None]
    ):
        super().__init__(parent)
        self.filename = filename
        self.is_dir = is_dir
        self.theme_mgr = theme_mgr
        self.on_apply = on_apply

        self.title(f"Права доступа (chmod) — {filename}")
        self.geometry("520x480")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Разбор начальных прав
        mode = initial_mode & 0o777 if initial_mode else (0o755 if is_dir else 0o644)

        self.var_u_r = tk.BooleanVar(value=bool(mode & 0o400))
        self.var_u_w = tk.BooleanVar(value=bool(mode & 0o200))
        self.var_u_x = tk.BooleanVar(value=bool(mode & 0o100))

        self.var_g_r = tk.BooleanVar(value=bool(mode & 0o040))
        self.var_g_w = tk.BooleanVar(value=bool(mode & 0o020))
        self.var_g_x = tk.BooleanVar(value=bool(mode & 0o010))

        self.var_o_r = tk.BooleanVar(value=bool(mode & 0o004))
        self.var_o_w = tk.BooleanVar(value=bool(mode & 0o002))
        self.var_o_x = tk.BooleanVar(value=bool(mode & 0o001))

        self.var_recursive = tk.BooleanVar(value=False)
        self.var_octal = tk.StringVar(value=oct(mode)[2:].zfill(3))
        self.var_symbolic = tk.StringVar(value="")

        self._build_ui()
        self._update_symbolic_display()
        self._center_window(parent)

    def _center_window(self, parent):
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() - 520) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - 480) // 2
            self.geometry(f"+{max(20, x)}+{max(20, y)}")
        except Exception:
            pass

    def _build_ui(self):
        c = self.theme_mgr.colors
        self.configure(bg=c["bg"])

        main_card = ttk.Frame(self, style="Card.TFrame", padding=20)
        main_card.pack(fill="both", expand=True, padx=12, pady=12)

        # Заголовок с иконкой
        lbl_head = ttk.Label(
            main_card,
            text=self.filename,
            font=(self.theme_mgr.display_font, 12, "bold")
        )
        lbl_head.pack(anchor="w", pady=(0, 4))

        lbl_sub = ttk.Label(
            main_card,
            text="Настройте разрешения на чтение, запись и исполнение для категорий пользователей:",
            style="Subtitle.TLabel"
        )
        lbl_sub.pack(anchor="w", pady=(0, 12))

        # Матрица прав доступа
        matrix_frame = ttk.Frame(main_card, style="Surface.TFrame", padding=14)
        matrix_frame.pack(fill="x", pady=(0, 12))

        # Заголовки колонок
        ttk.Label(matrix_frame, text="", style="Dim.TLabel", background=c["surface_bg"], width=14).grid(row=0, column=0)
        ttk.Label(matrix_frame, text="Чтение (r)", font=(self.theme_mgr.ui_font, 9, "bold"), background=c["surface_bg"]).grid(row=0, column=1, padx=12, pady=4)
        ttk.Label(matrix_frame, text="Запись (w)", font=(self.theme_mgr.ui_font, 9, "bold"), background=c["surface_bg"]).grid(row=0, column=2, padx=12, pady=4)
        ttk.Label(matrix_frame, text="Исполнение (x)", font=(self.theme_mgr.ui_font, 9, "bold"), background=c["surface_bg"]).grid(row=0, column=3, padx=12, pady=4)

        # Строка 1: Владелец
        ttk.Label(matrix_frame, text="Владелец (Owner):", font=(self.theme_mgr.ui_font, 9, "bold"), background=c["surface_bg"]).grid(row=1, column=0, sticky="w", pady=4)
        self._add_cb(matrix_frame, self.var_u_r, 1, 1)
        self._add_cb(matrix_frame, self.var_u_w, 1, 2)
        self._add_cb(matrix_frame, self.var_u_x, 1, 3)

        # Строка 2: Группа
        ttk.Label(matrix_frame, text="Группа (Group):", font=(self.theme_mgr.ui_font, 9, "bold"), background=c["surface_bg"]).grid(row=2, column=0, sticky="w", pady=4)
        self._add_cb(matrix_frame, self.var_g_r, 2, 1)
        self._add_cb(matrix_frame, self.var_g_w, 2, 2)
        self._add_cb(matrix_frame, self.var_g_x, 2, 3)

        # Строка 3: Остальные
        ttk.Label(matrix_frame, text="Остальные (Others):", font=(self.theme_mgr.ui_font, 9, "bold"), background=c["surface_bg"]).grid(row=3, column=0, sticky="w", pady=4)
        self._add_cb(matrix_frame, self.var_o_r, 3, 1)
        self._add_cb(matrix_frame, self.var_o_w, 3, 2)
        self._add_cb(matrix_frame, self.var_o_x, 3, 3)

        # Блок числового кода и символьного формата
        code_box = ttk.Frame(main_card, style="Card.TFrame")
        code_box.pack(fill="x", pady=(0, 12))

        ttk.Label(code_box, text="Код chmod:", style="FieldLabel.TLabel").pack(side="left", padx=(0, 6))
        self.entry_octal = ttk.Entry(code_box, textvariable=self.var_octal, width=6, font=(self.theme_mgr.mono_font, 11, "bold"))
        self.entry_octal.pack(side="left", padx=(0, 10))
        self.entry_octal.bind("<KeyRelease>", self._on_octal_entry_change)

        self.lbl_symbolic = ttk.Label(
            code_box,
            textvariable=self.var_symbolic,
            style="Badge.TLabel",
            font=(self.theme_mgr.mono_font, 10, "bold")
        )
        self.lbl_symbolic.pack(side="left")

        # Блок готовых пресетов
        preset_box = ttk.Frame(main_card, style="Card.TFrame")
        preset_box.pack(fill="x", pady=(0, 12))

        ttk.Label(preset_box, text="Быстрые пресеты:", style="FieldLabel.TLabel").pack(anchor="w", pady=(0, 6))

        pills_frame = ttk.Frame(preset_box, style="Card.TFrame")
        pills_frame.pack(fill="x")

        presets = [
            ("644 (Файл)", 0o644),
            ("755 (Папка / Скрипт)", 0o755),
            ("600 (.env / Ключ)", 0o600),
            ("444 (Read-Only)", 0o444),
            ("777 (Все права)", 0o777),
        ]
        for name, val in presets:
            btn = ttk.Button(
                pills_frame,
                text=name,
                style="Pill.TButton",
                command=lambda v=val: self._apply_preset(v)
            )
            btn.pack(side="left", padx=(0, 4), pady=2)

        # Опция рекурсивного применения (для папок)
        if self.is_dir:
            cb_rec = ttk.Checkbutton(
                main_card,
                text="Применить рекурсивно ко всем вложенным подпапкам и файлам",
                variable=self.var_recursive
            )
            cb_rec.pack(anchor="w", pady=(0, 12))

        # Нижняя панель действий
        bottom_bar = ttk.Frame(main_card, style="Card.TFrame")
        bottom_bar.pack(fill="x", pady=(4, 0))

        btn_cancel = ttk.Button(bottom_bar, text="Отмена", style="TButton", command=self.destroy)
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_apply = ttk.Button(bottom_bar, text="Применить", style="Primary.TButton", command=self._submit)
        btn_apply.pack(side="right")

    def _add_cb(self, parent, var: tk.BooleanVar, r: int, c: int):
        cb = ttk.Checkbutton(parent, variable=var, command=self._update_octal_from_checkboxes)
        cb.grid(row=r, column=c, padx=12, pady=4)

    def _update_symbolic_display(self):
        u_r = "r" if self.var_u_r.get() else "-"
        u_w = "w" if self.var_u_w.get() else "-"
        u_x = "x" if self.var_u_x.get() else "-"

        g_r = "r" if self.var_g_r.get() else "-"
        g_w = "w" if self.var_g_w.get() else "-"
        g_x = "x" if self.var_g_x.get() else "-"

        o_r = "r" if self.var_o_r.get() else "-"
        o_w = "w" if self.var_o_w.get() else "-"
        o_x = "x" if self.var_o_x.get() else "-"

        prefix = "d" if self.is_dir else "-"
        self.var_symbolic.set(f"{prefix}{u_r}{u_w}{u_x}{g_r}{g_w}{g_x}{o_r}{o_w}{o_x}")

    def _update_octal_from_checkboxes(self):
        u = (4 if self.var_u_r.get() else 0) + (2 if self.var_u_w.get() else 0) + (1 if self.var_u_x.get() else 0)
        g = (4 if self.var_g_r.get() else 0) + (2 if self.var_g_w.get() else 0) + (1 if self.var_g_x.get() else 0)
        o = (4 if self.var_o_r.get() else 0) + (2 if self.var_o_w.get() else 0) + (1 if self.var_o_x.get() else 0)
        oct_code = f"{u}{g}{o}"
        self.var_octal.set(oct_code)
        self._update_symbolic_display()

    def _on_octal_entry_change(self, event=None):
        val = self.var_octal.get().strip()
        if len(val) == 3 and val.isdigit():
            try:
                code = int(val, 8)
                self.var_u_r.set(bool(code & 0o400))
                self.var_u_w.set(bool(code & 0o200))
                self.var_u_x.set(bool(code & 0o100))

                self.var_g_r.set(bool(code & 0o040))
                self.var_g_w.set(bool(code & 0o020))
                self.var_g_x.set(bool(code & 0o010))

                self.var_o_r.set(bool(code & 0o004))
                self.var_o_w.set(bool(code & 0o002))
                self.var_o_x.set(bool(code & 0o001))
                self._update_symbolic_display()
            except Exception:
                pass

    def _apply_preset(self, mode: int):
        self.var_octal.set(oct(mode)[2:].zfill(3))
        self._on_octal_entry_change()

    def _submit(self):
        val = self.var_octal.get().strip()
        try:
            mode = int(val, 8)
            recursive = self.var_recursive.get()
            self.on_apply(mode, recursive)
            self.destroy()
        except ValueError:
            messagebox.showerror(
                "Ошибка",
                "Числовой код прав должен состоять из 3 восьмеричных цифр (например, 755 или 644).",
                parent=self
            )
