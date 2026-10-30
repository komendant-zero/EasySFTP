"""
Окно управления пользователями SFTP-сервера в современном дизайне.
Поддерживает:
- Назначение нескольких директорий (Multi-Directory)
- Режим изолированной песочницы (Sandbox)
- Режим только для чтения (Read-Only)
- Генератор надёжных паролей в один клик
- Копирование карточки доступа и готового Bash-скрипта (Bind Mounts)
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional, List, Callable, Any

from core.server_user_manager import ServerUserManager, ManagedUser, generate_secure_password
from ui.theme import ThemeManager


class UserManagerWindow(tk.Toplevel):
    """
    Панель администратора для управления пользователями, мульти-папками и песочницей.
    """
    def __init__(
        self,
        parent: tk.Tk,
        server_user_mgr: ServerUserManager,
        theme_mgr: ThemeManager,
        current_server_host: str,
        current_server_port: int,
        server_directories: Optional[List[str]] = None
    ):
        super().__init__(parent)
        self.mgr = server_user_mgr
        self.theme_mgr = theme_mgr
        self.host = current_server_host
        self.port = current_server_port
        self.server_dirs = [d for d in (server_directories or ["/", "/website", "/scripts", "/uploads", "/var/www/html"]) if d]

        self.title("Управление пользователями")
        self.geometry("980x620")
        self.minsize(840, 520)
        self.transient(parent)

        self._build_ui()
        self._center_window(parent)
        self._refresh_users_table()

    def _center_window(self, parent):
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() - 980) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - 620) // 2
            self.geometry(f"+{max(20, x)}+{max(20, y)}")
        except Exception:
            pass

    def _build_ui(self):
        c = self.theme_mgr.colors
        self.configure(bg=c["bg"])

        # -------------------------------------------------------------
        # Верхняя информационная панель
        # -------------------------------------------------------------
        header = ttk.Frame(self, style="Card.TFrame", padding=(20, 14))
        header.pack(fill="x", padx=14, pady=(14, 10))

        left_hd = ttk.Frame(header, style="Card.TFrame")
        left_hd.pack(side="left")

        lbl_head = ttk.Label(
            left_hd,
            text=f"Пользователи сервера: {self.host}:{self.port}",
            font=(self.theme_mgr.display_font, 13, "bold")
        )
        lbl_head.pack(anchor="w")

        lbl_sub = ttk.Label(
            left_hd,
            text="Создавайте изолированные учётные записи с разграничением директорий и прав",
            style="Subtitle.TLabel"
        )
        lbl_sub.pack(anchor="w", pady=(2, 0))

        btn_add = ttk.Button(
            header,
            text="+ Создать пользователя",
            style="Primary.TButton",
            command=self._open_create_user_dialog
        )
        btn_add.pack(side="right")

        # -------------------------------------------------------------
        # Основная область (Таблица слева + Карточка справа)
        # -------------------------------------------------------------
        body = ttk.Frame(self, style="Main.TFrame")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        # Левая часть: Таблица пользователей
        left_box = ttk.Frame(body, style="Card.TFrame", padding=2)
        left_box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        columns = ("user", "dirs", "mode")
        self.tree = ttk.Treeview(left_box, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("user", text="Логин пользователя", anchor="w")
        self.tree.heading("dirs", text="Разрешённые директории", anchor="w")
        self.tree.heading("mode", text="Режим работы", anchor="w")

        self.tree.column("user", width=160, anchor="w")
        self.tree.column("dirs", width=260, anchor="w")
        self.tree.column("mode", width=180, anchor="w")

        scroll_y = ttk.Scrollbar(left_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        self.tree.bind("<<TreeviewSelect>>", self._on_user_selected)

        # Правая часть: Карточка выбранного пользователя
        self.right_card = ttk.Frame(body, style="Card.TFrame", width=360, padding=18)
        self.right_card.pack(side="right", fill="both")

        self.lbl_card_title = ttk.Label(
            self.right_card,
            text="Реквизиты и настройки",
            font=(self.theme_mgr.display_font, 12, "bold")
        )
        self.lbl_card_title.pack(anchor="w", pady=(0, 10))

        self.lbl_card_details = ttk.Label(
            self.right_card,
            text="Выберите пользователя в таблице слева для просмотра параметров и передачи реквизитов.",
            style="Dim.TLabel",
            wraplength=320,
            justify="left"
        )
        self.lbl_card_details.pack(anchor="w", fill="both", expand=True, pady=(0, 14))

        # Кнопки действий карточки
        self.btn_copy_card = ttk.Button(
            self.right_card,
            text="Скопировать реквизиты",
            style="Primary.TButton",
            state="disabled",
            command=self._copy_user_credentials
        )
        self.btn_copy_card.pack(fill="x", pady=4)

        self.btn_copy_script = ttk.Button(
            self.right_card,
            text="Скопировать Linux-скрипт (Bind Mounts)",
            style="TButton",
            state="disabled",
            command=self._copy_setup_script
        )
        self.btn_copy_script.pack(fill="x", pady=4)

        self.btn_delete_user = ttk.Button(
            self.right_card,
            text="Удалить пользователя",
            style="Danger.TButton",
            state="disabled",
            command=self._delete_selected_user
        )
        self.btn_delete_user.pack(fill="x", pady=(12, 4))

        self.selected_user: Optional[ManagedUser] = None

    def _refresh_users_table(self):
        c = self.theme_mgr.colors
        self.tree.delete(*self.tree.get_children())
        self.tree.tag_configure("even", background=c["tree_bg"])
        self.tree.tag_configure("odd", background=c["tree_alt_bg"])

        users = self.mgr.get_users()
        for i, u in enumerate(users):
            tag = "odd" if i % 2 == 1 else "even"
            dirs_str = ", ".join(u.allowed_directories)
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(u.username, dirs_str, u.mode_badge),
                tags=(tag,)
            )

        if users:
            self.tree.selection_set("0")
            self._on_user_selected()
        else:
            self._on_user_selected()

    def _on_user_selected(self, event=None):
        sel = self.tree.selection()
        if not sel:
            self.selected_user = None
            self.lbl_card_title.config(text="Реквизиты и настройки")
            self.lbl_card_details.config(text="Пользователи пока не выбраны.")
            self.btn_copy_card.config(state="disabled")
            self.btn_copy_script.config(state="disabled")
            self.btn_delete_user.config(state="disabled")
            return

        idx = int(sel[0])
        users = self.mgr.get_users()
        if 0 <= idx < len(users):
            u = users[idx]
            self.selected_user = u
            self.lbl_card_title.config(text=f"Пользователь: {u.username}")

            dirs_bullet = "\n".join(f"   • {d}" for d in u.allowed_directories)

            info = (
                f"Хост: {self.host}:{self.port}\n"
                f"Логин: {u.username}\n"
                f"Пароль: {u.password}\n\n"
                f"Режим: {u.mode_display}\n\n"
                f"Разрешённые папки ({len(u.allowed_directories)}):\n"
                f"{dirs_bullet}\n\n"
            )
            if u.mode == "sandbox":
                info += "В режиме песочницы пользователь имеет полную свободу внутри назначенных папок, но изолирован от остального сервера (chroot jail)."
            elif u.mode == "read_only":
                info += "В режиме Read-Only пользователь может только просматривать и скачивать файлы без права изменения."

            self.lbl_card_details.config(text=info)
            self.btn_copy_card.config(state="normal")
            self.btn_copy_script.config(state="normal")
            self.btn_delete_user.config(state="normal")

    def _copy_user_credentials(self):
        if not self.selected_user:
            return
        u = self.selected_user
        dirs_str = ", ".join(u.allowed_directories)
        card_text = (
            f"Реквизиты для подключения по SFTP:\n"
            f"Host: {self.host}\n"
            f"Port: {self.port}\n"
            f"User name: {u.username}\n"
            f"Password: {u.password}\n"
            f"Разрешённые папки: {dirs_str}\n"
            f"Режим доступа: {u.mode_display}"
        )
        self.clipboard_clear()
        self.clipboard_append(card_text)
        messagebox.showinfo(
            "Скопировано",
            "Реквизиты скопированы в буфер обмена!\nОтправьте их пользователю для входа через EasySFTP или AmneziaVPN.",
            parent=self
        )

    def _copy_setup_script(self):
        if not self.selected_user:
            return
        script = self.mgr.generate_linux_setup_script(self.selected_user)
        self.clipboard_clear()
        self.clipboard_append(script)
        messagebox.showinfo(
            "Скопировано",
            "Готовый Linux Bash-скрипт с монтированием папок (bind mounts) скопирован в буфер обмена!",
            parent=self
        )

    def _delete_selected_user(self):
        if not self.selected_user:
            return
        username = self.selected_user.username
        ans = messagebox.askyesno("Удаление", f"Удалить пользователя '{username}'?", parent=self)
        if ans:
            self.mgr.delete_user(username)
            self._refresh_users_table()

    # -------------------------------------------------------------
    # Модальное окно создания пользователя
    # -------------------------------------------------------------

    def _open_create_user_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Создание нового пользователя SFTP")
        dlg.geometry("600x620")
        dlg.minsize(540, 540)
        dlg.transient(self)
        dlg.grab_set()

        c = self.theme_mgr.colors
        dlg.configure(bg=c["bg"])

        box = ttk.Frame(dlg, style="Card.TFrame", padding=22)
        box.pack(fill="both", expand=True, padx=14, pady=14)

        lbl_title = ttk.Label(
            box,
            text="Создание пользователя SFTP",
            font=(self.theme_mgr.display_font, 13, "bold")
        )
        lbl_title.pack(anchor="w", pady=(0, 4))

        lbl_sub = ttk.Label(
            box,
            text="Задайте логин, пароль и укажите папки с правами доступа",
            style="Subtitle.TLabel"
        )
        lbl_sub.pack(anchor="w", pady=(0, 14))

        # 1. Логин
        ttk.Label(box, text="Имя пользователя (Логин):", style="FieldLabel.TLabel").pack(anchor="w", pady=(2, 2))
        entry_uname = ttk.Entry(box)
        entry_uname.pack(fill="x", pady=(0, 8))
        entry_uname.insert(0, "client_user")

        # 2. Пароль с кнопкой генерации
        ttk.Label(box, text="Пароль:", style="FieldLabel.TLabel").pack(anchor="w", pady=(2, 2))
        pass_row = ttk.Frame(box, style="Card.TFrame")
        pass_row.pack(fill="x", pady=(0, 10))

        entry_pwd = ttk.Entry(pass_row)
        entry_pwd.pack(side="left", fill="x", expand=True)
        entry_pwd.insert(0, generate_secure_password(12))

        btn_gen = ttk.Button(
            pass_row,
            text="Сгенерировать",
            style="Tool.TButton",
            command=lambda: (entry_pwd.delete(0, tk.END), entry_pwd.insert(0, generate_secure_password(12)))
        )
        btn_gen.pack(side="right", padx=(6, 0))

        # 3. Режим работы
        ttk.Label(box, text="Режим работы пользователя:", style="FieldLabel.TLabel").pack(anchor="w", pady=(2, 2))
        var_mode = tk.StringVar(value="sandbox")

        mode_box = ttk.Frame(box, style="Surface.TFrame", padding=10)
        mode_box.pack(fill="x", pady=(0, 12))

        ttk.Radiobutton(
            mode_box,
            text="Изолированная песочница (Sandbox) — доступ только к назначенным папкам",
            variable=var_mode,
            value="sandbox"
        ).pack(anchor="w", pady=2)

        ttk.Radiobutton(
            mode_box,
            text="Только чтение (Read-Only) — просмотр и скачивание без изменений",
            variable=var_mode,
            value="read_only"
        ).pack(anchor="w", pady=2)

        ttk.Radiobutton(
            mode_box,
            text="Доступ ко всему серверу (Full Access) — без изоляции",
            variable=var_mode,
            value="full"
        ).pack(anchor="w", pady=2)

        # 4. Выбор разрешённых папок
        ttk.Label(box, text="Разрешённые директории:", style="FieldLabel.TLabel").pack(anchor="w", pady=(2, 2))
        dirs_box = ttk.Frame(box, style="Surface.TFrame", padding=10)
        dirs_box.pack(fill="both", expand=True, pady=(0, 14))

        dir_vars = {}
        for d in self.server_dirs:
            var = tk.BooleanVar(value=(d in ["/website", "/uploads", "/var/www/html"]))
            dir_vars[d] = var
            cb = ttk.Checkbutton(dirs_box, text=d, variable=var)
            cb.pack(anchor="w", pady=2)

        # Добавление своей папки
        custom_row = ttk.Frame(dirs_box, style="Surface.TFrame")
        custom_row.pack(fill="x", pady=(6, 2))

        entry_custom = ttk.Entry(custom_row)
        entry_custom.pack(side="left", fill="x", expand=True)
        entry_custom.insert(0, "/data/media")

        def add_custom_dir():
            cdir = entry_custom.get().strip()
            if cdir and cdir not in dir_vars:
                cvar = tk.BooleanVar(value=True)
                dir_vars[cdir] = cvar
                ttk.Checkbutton(dirs_box, text=cdir, variable=cvar).pack(anchor="w", pady=2)
                entry_custom.delete(0, tk.END)

        btn_add_dir = ttk.Button(custom_row, text="+ Добавить папку", style="Tool.TButton", command=add_custom_dir)
        btn_add_dir.pack(side="right", padx=(6, 0))

        # 5. Кнопки сохранения / отмены
        bottom_row = ttk.Frame(box, style="Card.TFrame")
        bottom_row.pack(fill="x")

        btn_cancel = ttk.Button(bottom_row, text="Отмена", style="TButton", command=dlg.destroy)
        btn_cancel.pack(side="right", padx=(8, 0))

        def on_create():
            uname = entry_uname.get().strip()
            pwd = entry_pwd.get().strip()
            mode = var_mode.get()

            if not uname:
                messagebox.showwarning("Внимание", "Укажите имя пользователя!", parent=dlg)
                return
            if not pwd:
                messagebox.showwarning("Внимание", "Укажите пароль!", parent=dlg)
                return

            chosen_dirs = [d for d, v in dir_vars.items() if v.get()]
            if not chosen_dirs:
                chosen_dirs = ["/"]

            try:
                self.mgr.create_user(username=uname, password=pwd, allowed_dirs=chosen_dirs, mode=mode)
                self._refresh_users_table()
                dlg.destroy()
                messagebox.showinfo(
                    "Успех",
                    f"Пользователь '{uname}' успешно создан!\n\n"
                    f"Вы можете скопировать реквизиты кнопкой в карточке справа.",
                    parent=self
                )
            except Exception as e:
                messagebox.showerror("Ошибка создания", str(e), parent=dlg)

        btn_save = ttk.Button(bottom_row, text="Создать пользователя", style="Primary.TButton", command=on_create)
        btn_save.pack(side="right")
