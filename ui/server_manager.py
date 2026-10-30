"""
Менеджер закладок серверов в современном стиле.
Позволяет сохранять подключения, быстро находить нужный сервер через поиск,
редактировать параметры и входить в один клик.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional, Dict, Any, List

from core.config_manager import ConfigManager
from ui.theme import ThemeManager


class ServerManagerDialog(tk.Toplevel):
    """
    Окно управления сохранёнными подключениями к SFTP серверам.
    """
    def __init__(
        self,
        parent: tk.Tk,
        config_mgr: ConfigManager,
        theme_mgr: ThemeManager,
        on_connect: Callable[[Dict[str, Any]], None]
    ):
        super().__init__(parent)
        self.config_mgr = config_mgr
        self.theme_mgr = theme_mgr
        self.on_connect = on_connect
        self.selected_server_id: Optional[str] = None
        self.servers_cache: List[Dict[str, Any]] = []

        self.title("Менеджер серверов")
        self.geometry("820x520")
        self.minsize(720, 440)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._load_servers_list()
        self._center_window(parent)

    def _center_window(self, parent):
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() - 820) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - 520) // 2
            self.geometry(f"+{max(20, x)}+{max(20, y)}")
        except Exception:
            pass

    def _build_ui(self):
        c = self.theme_mgr.colors
        self.configure(bg=c["bg"])

        main_box = ttk.Frame(self, style="Main.TFrame")
        main_box.pack(fill="both", expand=True, padx=14, pady=14)

        # -------------------------------------------------------------
        # Левая колонка: Список закладок и поиск
        # -------------------------------------------------------------
        left_card = ttk.Frame(main_box, style="Card.TFrame", width=280, padding=12)
        left_card.pack(side="left", fill="both", padx=(0, 10))

        lbl_list_title = ttk.Label(
            left_card,
            text="Сохранённые серверы",
            font=(self.theme_mgr.display_font, 11, "bold")
        )
        lbl_list_title.pack(anchor="w", pady=(0, 8))

        # Поле поиска по серверам
        search_box = ttk.Frame(left_card, style="Card.TFrame")
        search_box.pack(fill="x", pady=(0, 8))

        self.entry_search = ttk.Entry(search_box, font=(self.theme_mgr.ui_font, 9))
        self.entry_search.pack(fill="x")
        self.entry_search.insert(0, "")
        self.entry_search.bind("<KeyRelease>", lambda e: self._filter_servers())

        # Список Listbox
        list_container = ttk.Frame(left_card, style="Card.TFrame")
        list_container.pack(fill="both", expand=True, pady=(0, 8))

        self.server_listbox = tk.Listbox(
            list_container,
            bg=c["surface_bg"],
            fg=c["fg"],
            selectbackground=c["accent"],
            selectforeground="#ffffff",
            relief="flat",
            font=(self.theme_mgr.ui_font, 10),
            borderwidth=1,
            highlightthickness=0,
            activestyle="none"
        )
        self.server_listbox.pack(side="left", fill="both", expand=True)
        self.server_listbox.bind("<<ListboxSelect>>", self._on_select_server)

        scroll_servers = ttk.Scrollbar(list_container, orient="vertical", command=self.server_listbox.yview)
        self.server_listbox.configure(yscrollcommand=scroll_servers.set)
        scroll_servers.pack(side="right", fill="y")

        # Кнопки под списком
        btn_list_box = ttk.Frame(left_card, style="Card.TFrame")
        btn_list_box.pack(fill="x")

        btn_add = ttk.Button(btn_list_box, text="+ Добавить", style="TButton", command=self._on_new_server)
        btn_add.pack(side="left", fill="x", expand=True, padx=(0, 4))

        btn_del = ttk.Button(btn_list_box, text="Удалить", style="Danger.TButton", command=self._on_delete_server)
        btn_del.pack(side="right", fill="x", expand=True)

        # -------------------------------------------------------------
        # Правая колонка: Форма редактирования сервера
        # -------------------------------------------------------------
        right_card = ttk.Frame(main_box, style="Card.TFrame", padding=18)
        right_card.pack(side="right", fill="both", expand=True)

        lbl_form_title = ttk.Label(
            right_card,
            text="Параметры подключения",
            font=(self.theme_mgr.display_font, 12, "bold")
        )
        lbl_form_title.pack(anchor="w", pady=(0, 14))

        form_grid = ttk.Frame(right_card, style="Card.TFrame")
        form_grid.pack(fill="both", expand=True)

        # 1. Имя закладки
        ttk.Label(form_grid, text="Название закладки:", style="FieldLabel.TLabel").grid(row=0, column=0, sticky="w", pady=4)
        self.entry_name = ttk.Entry(form_grid)
        self.entry_name.grid(row=0, column=1, sticky="ew", pady=4)

        # 2. Хост
        ttk.Label(form_grid, text="Хост (IP или домен):", style="FieldLabel.TLabel").grid(row=1, column=0, sticky="w", pady=4)
        self.entry_host = ttk.Entry(form_grid)
        self.entry_host.grid(row=1, column=1, sticky="ew", pady=4)

        # 3. Порт
        ttk.Label(form_grid, text="Порт:", style="FieldLabel.TLabel").grid(row=2, column=0, sticky="w", pady=4)
        self.entry_port = ttk.Entry(form_grid, width=10)
        self.entry_port.grid(row=2, column=1, sticky="w", pady=4)

        # 4. Логин
        ttk.Label(form_grid, text="Пользователь (Логин):", style="FieldLabel.TLabel").grid(row=3, column=0, sticky="w", pady=4)
        self.entry_user = ttk.Entry(form_grid)
        self.entry_user.grid(row=3, column=1, sticky="ew", pady=4)

        # 5. Тип авторизации
        ttk.Label(form_grid, text="Способ входа:", style="FieldLabel.TLabel").grid(row=4, column=0, sticky="w", pady=4)
        self.var_auth = tk.StringVar(value="password")
        auth_box = ttk.Frame(form_grid, style="Card.TFrame")
        auth_box.grid(row=4, column=1, sticky="w", pady=4)

        rb_pass = ttk.Radiobutton(auth_box, text="Пароль", variable=self.var_auth, value="password", command=self._toggle_auth_fields)
        rb_pass.pack(side="left", padx=(0, 12))
        rb_key = ttk.Radiobutton(auth_box, text="SSH-ключ", variable=self.var_auth, value="key", command=self._toggle_auth_fields)
        rb_key.pack(side="left")

        # 6. Пароль
        self.lbl_pass = ttk.Label(form_grid, text="Пароль:", style="FieldLabel.TLabel")
        self.lbl_pass.grid(row=5, column=0, sticky="w", pady=4)
        pass_row = ttk.Frame(form_grid, style="Card.TFrame")
        pass_row.grid(row=5, column=1, sticky="ew", pady=4)

        self.entry_pass = ttk.Entry(pass_row, show="●")
        self.entry_pass.pack(side="left", fill="x", expand=True)

        self.btn_toggle_pass = ttk.Button(pass_row, text="Показать", width=8, style="Tool.TButton", command=self._toggle_show_pass)
        self.btn_toggle_pass.pack(side="right", padx=(4, 0))

        # 7. Файл SSH-ключа
        self.lbl_key = ttk.Label(form_grid, text="Файл SSH-ключа:", style="FieldLabel.TLabel")
        self.lbl_key.grid(row=6, column=0, sticky="w", pady=4)
        key_row = ttk.Frame(form_grid, style="Card.TFrame")
        key_row.grid(row=6, column=1, sticky="ew", pady=4)

        self.entry_key = ttk.Entry(key_row)
        self.entry_key.pack(side="left", fill="x", expand=True)

        btn_browse_key = ttk.Button(key_row, text="Обзор...", style="Tool.TButton", command=self._browse_key_file)
        btn_browse_key.pack(side="right", padx=(4, 0))

        # 8. Начальная папка
        ttk.Label(form_grid, text="Папка на сервере:", style="FieldLabel.TLabel").grid(row=7, column=0, sticky="w", pady=4)
        self.entry_initial_dir = ttk.Entry(form_grid)
        self.entry_initial_dir.grid(row=7, column=1, sticky="ew", pady=4)

        form_grid.columnconfigure(1, weight=1)

        # Нижняя панель действий
        bottom_bar = ttk.Frame(right_card, style="Card.TFrame")
        bottom_bar.pack(fill="x", pady=(14, 0))

        self.btn_save_server = ttk.Button(bottom_bar, text="Сохранить", style="TButton", command=self._on_save_server)
        self.btn_save_server.pack(side="left")

        btn_close = ttk.Button(bottom_bar, text="Закрыть", style="TButton", command=self.destroy)
        btn_close.pack(side="right", padx=(8, 0))

        self.btn_connect_now = ttk.Button(
            bottom_bar,
            text="Подключиться",
            style="Primary.TButton",
            command=self._on_connect_now
        )
        self.btn_connect_now.pack(side="right")

        self._toggle_auth_fields()

    def _toggle_auth_fields(self):
        is_pass = self.var_auth.get() == "password"
        if is_pass:
            self.lbl_pass.grid()
            self.entry_pass.master.grid()
            self.lbl_key.grid_remove()
            self.entry_key.master.grid_remove()
        else:
            self.lbl_pass.grid_remove()
            self.entry_pass.master.grid_remove()
            self.lbl_key.grid()
            self.entry_key.master.grid()

    def _toggle_show_pass(self):
        if self.entry_pass.cget("show") == "":
            self.entry_pass.config(show="●")
            self.btn_toggle_pass.config(text="Показать")
        else:
            self.entry_pass.config(show="")
            self.btn_toggle_pass.config(text="Скрыть")

    def _browse_key_file(self):
        f = filedialog.askopenfilename(
            parent=self,
            title="Выберите приватный SSH-ключ",
            filetypes=[("Ключи SSH (*.pem, *.key, id_*)", "*.*")]
        )
        if f:
            self.entry_key.delete(0, tk.END)
            self.entry_key.insert(0, f)

    def _load_servers_list(self):
        self.servers_cache = self.config_mgr.get_servers()
        self._filter_servers()

    def _filter_servers(self):
        query = self.entry_search.get().strip().lower()
        self.server_listbox.delete(0, tk.END)
        self.visible_servers = []

        for s in self.servers_cache:
            name = s.get("name") or s.get("host", "")
            host = s.get("host", "")
            if not query or query in name.lower() or query in host.lower():
                self.visible_servers.append(s)
                self.server_listbox.insert(tk.END, f"{name} ({host})")

        if self.visible_servers:
            self.server_listbox.selection_set(0)
            self._fill_form_with_server(self.visible_servers[0])
        else:
            self._on_new_server()

    def _on_select_server(self, event=None):
        sel = self.server_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.visible_servers):
            self._fill_form_with_server(self.visible_servers[idx])

    def _fill_form_with_server(self, s: Dict[str, Any]):
        self.selected_server_id = s.get("id")
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, s.get("name", ""))

        self.entry_host.delete(0, tk.END)
        self.entry_host.insert(0, s.get("host", ""))

        self.entry_port.delete(0, tk.END)
        self.entry_port.insert(0, str(s.get("port", 22)))

        self.entry_user.delete(0, tk.END)
        self.entry_user.insert(0, s.get("username", "root"))

        auth = s.get("auth_type", "password")
        self.var_auth.set(auth)

        self.entry_pass.delete(0, tk.END)
        self.entry_pass.insert(0, s.get("password", ""))

        self.entry_key.delete(0, tk.END)
        self.entry_key.insert(0, s.get("key_path", ""))

        self.entry_initial_dir.delete(0, tk.END)
        self.entry_initial_dir.insert(0, s.get("initial_remote_path", "/"))

        self._toggle_auth_fields()

    def _on_new_server(self):
        self.selected_server_id = None
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, "Новый сервер")

        self.entry_host.delete(0, tk.END)
        self.entry_port.delete(0, tk.END)
        self.entry_port.insert(0, "22")

        self.entry_user.delete(0, tk.END)
        self.entry_user.insert(0, "root")

        self.var_auth.set("password")
        self.entry_pass.delete(0, tk.END)
        self.entry_key.delete(0, tk.END)
        self.entry_initial_dir.delete(0, tk.END)
        self.entry_initial_dir.insert(0, "/")

        self._toggle_auth_fields()
        self.entry_host.focus_set()

    def _on_save_server(self):
        name = self.entry_name.get().strip() or "Без названия"
        host = self.entry_host.get().strip()
        if not host:
            messagebox.showwarning("Внимание", "Пожалуйста, укажите хост сервера!", parent=self)
            self.entry_host.focus_set()
            return

        try:
            port = int(self.entry_port.get().strip() or "22")
        except ValueError:
            port = 22

        username = self.entry_user.get().strip() or "root"
        auth_type = self.var_auth.get()
        password = self.entry_pass.get() if auth_type == "password" else ""
        key_path = self.entry_key.get().strip() if auth_type == "key" else ""
        initial_remote_path = self.entry_initial_dir.get().strip() or "/"

        server_data = {
            "name": name,
            "host": host,
            "port": port,
            "username": username,
            "auth_type": auth_type,
            "password": password,
            "key_path": key_path,
            "initial_remote_path": initial_remote_path,
        }

        if self.selected_server_id:
            server_data["id"] = self.selected_server_id
            self.config_mgr.update_server(server_data)
        else:
            self.config_mgr.add_server(server_data)

        self._load_servers_list()
        messagebox.showinfo("Сохранено", f"Сервер '{name}' успешно сохранён!", parent=self)

    def _on_delete_server(self):
        if not self.selected_server_id:
            return
        ans = messagebox.askyesno("Удаление", "Удалить выбранный сервер из закладок?", parent=self)
        if ans:
            self.config_mgr.delete_server(self.selected_server_id)
            self._load_servers_list()

    def _on_connect_now(self):
        host = self.entry_host.get().strip()
        if not host:
            messagebox.showwarning("Внимание", "Укажите хост сервера!", parent=self)
            return

        try:
            port = int(self.entry_port.get().strip() or "22")
        except ValueError:
            port = 22

        s = {
            "host": host,
            "port": port,
            "username": self.entry_user.get().strip() or "root",
            "auth_type": self.var_auth.get(),
            "password": self.entry_pass.get(),
            "key_path": self.entry_key.get().strip(),
            "initial_remote_path": self.entry_initial_dir.get().strip() or "/"
        }
        self.destroy()
        self.on_connect(s)
