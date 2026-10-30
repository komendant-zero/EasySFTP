"""
Главное окно EasySFTP.
Современный дизайн в стиле мессенджера (Telegram / Slack / Discord):
- Вход на сервер в 1 клик при нажатии на карточку сервера
- Если на сервере было несколько пользователей — наглядный выбор пользователя для входа в 1 клик
- Чёткая и заметная кнопка «➕ Добавить сервер»
- Все тексты на кнопках лаконичны и гарантированно отображаются целиком
- Полнофункциональный проводник файлов с сортировкой колонок и редактором
"""

from __future__ import annotations
import os
import posixpath
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from typing import Dict, List, Optional, Any, Tuple

from core.file_utils import FileItem, format_size, is_text_file
from core.sftp_client import SFTPClient, CancelToken, translate_sftp_error
from core.local_client import LocalClient
from core.config_manager import ConfigManager
from core.demo_server import DemoSFTPClient
from core.clipboard_parser import parse_sftp_clipboard
from core.server_user_manager import ServerUserManager, ManagedUser
from ui.theme import ThemeManager, enable_high_dpi
from ui.editor_window import EditorWindow
from ui.permissions_dialog import PermissionsDialog
from ui.server_manager import ServerManagerDialog
from ui.user_manager_window import UserManagerWindow
from ui.help_window import HelpWindow


class EasySFTPApp:
    """
    Главный контроллер приложения EasySFTP.
    """
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("EasySFTP — Профессиональный SFTP-клиент")
        self.root.geometry("1060x680")
        self.root.minsize(880, 560)

        enable_high_dpi()

        # Инициализация ядра
        self.config_mgr = ConfigManager()
        saved_theme = self.config_mgr.get_setting("theme", "dark")
        self.theme_mgr = ThemeManager(saved_theme)

        self.local_client = LocalClient()
        self.real_sftp = SFTPClient()
        self.demo_sftp = DemoSFTPClient()
        self.active_client: Any = self.real_sftp

        self.current_remote_items: List[FileItem] = []
        self.filtered_remote_items: List[FileItem] = []
        self.sort_column = ""
        self.sort_reverse = False

        self.cancel_token: Optional[CancelToken] = None
        self.work_queue: queue.Queue = queue.Queue()

        self.selected_key_path = ""
        self.auth_mode = "password"

        # Состояние выбранного сервера для мульти-пользовательского выбора
        self.active_server_group: Optional[Dict[str, Any]] = None

        # Главный контейнер
        self.main_container = ttk.Frame(self.root, style="Main.TFrame")
        self.main_container.pack(fill="both", expand=True)

        self._build_top_app_header()
        self._build_connect_screen()
        self._build_files_screen()

        self.theme_mgr.apply(self.root)

        # Загрузка последнего подключения и списка серверов
        self._load_last_connection()
        self._refresh_recent_servers_list()

        # Показываем экран подключения
        self._show_screen("connect")

        self._queue_after_id = None
        self._schedule_queue_process()
        self.root.bind("<F2>", self._on_f2_pressed)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_app)

    def _schedule_queue_process(self):
        try:
            if self.root.winfo_exists():
                self._queue_after_id = self.root.after(100, self._process_queue)
        except Exception:
            pass

    # -----------------------------------------------------------------
    # Универсальная верхняя панель приложения
    # -----------------------------------------------------------------

    def _build_top_app_header(self):
        self.top_header = ttk.Frame(self.main_container, style="Card.TFrame", padding=(16, 8))
        self.top_header.pack(fill="x", side="top", pady=(0, 2))

        # Левая часть: логотип и статус
        left_h = ttk.Frame(self.top_header, style="Card.TFrame")
        left_h.pack(side="left")

        lbl_logo = ttk.Label(
            left_h,
            text="EasySFTP",
            font=(self.theme_mgr.display_font, 13, "bold")
        )
        lbl_logo.pack(side="left")

        lbl_ver = ttk.Label(
            left_h,
            text="v2.1",
            style="Badge.TLabel"
        )
        lbl_ver.pack(side="left", padx=(8, 12))

        self.lbl_header_subtitle = ttk.Label(
            left_h,
            text="SFTP-клиент",
            style="Subtitle.TLabel"
        )
        self.lbl_header_subtitle.pack(side="left")

        # Правая часть: лаконичные кнопки панели
        self.right_h = ttk.Frame(self.top_header, style="Card.TFrame")
        self.right_h.pack(side="right")

        self.btn_header_servers = ttk.Button(
            self.right_h,
            text="Серверы",
            style="Tool.TButton",
            command=self._open_server_manager
        )
        self.btn_header_servers.pack(side="left", padx=3)

        self.btn_header_theme = ttk.Button(
            self.right_h,
            text="Тема",
            style="Tool.TButton",
            command=self._toggle_theme
        )
        self.btn_header_theme.pack(side="left", padx=3)

        self.btn_header_help = ttk.Button(
            self.right_h,
            text="Справка",
            style="Tool.TButton",
            command=self._open_help
        )
        self.btn_header_help.pack(side="left", padx=3)

        self.btn_header_users = ttk.Button(
            self.right_h,
            text="Пользователи",
            style="Primary.TButton",
            command=self._open_user_manager
        )

        self.btn_header_disconnect = ttk.Button(
            self.right_h,
            text="Отключиться",
            style="Danger.TButton",
            command=self._disconnect
        )

    def _show_screen(self, screen_name: str):
        if screen_name == "connect":
            self.frame_files.pack_forget()
            self.frame_connect.pack(fill="both", expand=True)
            self.root.title("EasySFTP — Подключение")
            self.lbl_header_subtitle.config(text="SFTP-клиент")

            self.btn_header_servers.pack(side="left", padx=3)
            self.btn_header_users.pack_forget()
            self.btn_header_disconnect.pack_forget()

            self._refresh_recent_servers_list()
        else:
            self.frame_connect.pack_forget()
            self.frame_files.pack(fill="both", expand=True)

            host = self.active_client.current_host
            user = getattr(self.active_client, "current_user", "")
            port = self.active_client.current_port
            is_demo = (self.active_client == self.demo_sftp)

            status_text = f"● {host}:{port} ({user})" if not is_demo else "● Демо-песочница"
            self.lbl_header_subtitle.config(text=status_text)
            self.root.title(f"EasySFTP — {host}:{port}")

            self.btn_header_servers.pack(side="left", padx=3)
            self.btn_header_users.pack(side="left", padx=4)
            self.btn_header_disconnect.pack(side="left", padx=3)

    # -----------------------------------------------------------------
    # ЭКРАН 1: Подключение в стиле мессенджера (Telegram / Slack)
    # -----------------------------------------------------------------

    def _build_connect_screen(self):
        c = self.theme_mgr.colors
        self.frame_connect = ttk.Frame(self.main_container, style="Main.TFrame")

        # -------------------------------------------------------------
        # ЛЕВАЯ КОЛОНКА: Список серверов («чатов»)
        # -------------------------------------------------------------
        self.messenger_sidebar = ttk.Frame(self.frame_connect, style="Sidebar.TFrame", width=340)
        self.messenger_sidebar.pack(side="left", fill="y", padx=(12, 6), pady=10)
        self.messenger_sidebar.pack_propagate(False)

        # 1. Поиск по серверам
        search_top_bar = ttk.Frame(self.messenger_sidebar, style="Card.TFrame", padding=(10, 8))
        search_top_bar.pack(fill="x")

        search_input_frame = ttk.Frame(search_top_bar, style="Surface.TFrame", padding=(6, 4))
        search_input_frame.pack(fill="x")

        ttk.Label(search_input_frame, text="🔍", background=c["surface_bg"]).pack(side="left", padx=(2, 6))
        self.entry_server_search = ttk.Entry(
            search_input_frame,
            font=(self.theme_mgr.ui_font, 10)
        )
        self.entry_server_search.pack(side="left", fill="x", expand=True)
        self.entry_server_search.bind("<KeyRelease>", lambda e: self._refresh_recent_servers_list())

        # 2. Главная кнопка «+ Добавить сервер»
        btn_add_server = ttk.Button(
            self.messenger_sidebar,
            text="+ Добавить сервер",
            style="Primary.TButton",
            command=self._show_new_connection_form
        )
        btn_add_server.pack(fill="x", padx=10, pady=(4, 8))

        # 3. Скроллируемая лента серверов
        list_container = ttk.Frame(self.messenger_sidebar, style="Card.TFrame")
        list_container.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self.server_canvas = tk.Canvas(
            list_container,
            bg=c["card_bg"],
            highlightthickness=0,
            borderwidth=0
        )
        self.server_canvas.pack(side="left", fill="both", expand=True)

        scrollbar_servers = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.server_canvas.yview
        )
        scrollbar_servers.pack(side="right", fill="y")
        self.server_canvas.configure(yscrollcommand=scrollbar_servers.set)

        self.server_list_inner = ttk.Frame(self.server_canvas, style="Card.TFrame")
        self.server_canvas_window = self.server_canvas.create_window(
            (0, 0),
            window=self.server_list_inner,
            anchor="nw"
        )

        self.server_list_inner.bind("<Configure>", self._on_server_list_configure)
        self.server_canvas.bind("<Configure>", self._on_canvas_configure)
        self.server_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # -------------------------------------------------------------
        # ПРАВАЯ ОБЛАСТЬ: Выбор пользователя или форма добавления сервера
        # -------------------------------------------------------------
        self.right_workspace = ttk.Frame(self.frame_connect, style="Card.TFrame", padding=20)
        self.right_workspace.pack(side="right", fill="both", expand=True, padx=(6, 12), pady=10)

        # 1. Панель: Выбор пользователя (если на сервере было несколько пользователей)
        self.pane_user_picker = ttk.Frame(self.right_workspace, style="Card.TFrame")

        # 2. Панель: Форма нового подключения («Добавить сервер»)
        self.pane_new_connection = ttk.Frame(self.right_workspace, style="Card.TFrame")

        self._build_user_picker_pane()
        self._build_new_connection_pane()

        # По умолчанию показываем форму добавления нового сервера
        self._show_new_connection_form()

    def _on_server_list_configure(self, event=None):
        self.server_canvas.configure(scrollregion=self.server_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.server_canvas.itemconfig(self.server_canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        try:
            if self.frame_connect.winfo_ismapped():
                self.server_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    # -----------------------------------------------------------------
    # Группировка серверов по адресу (host:port) и списку пользователей
    # -----------------------------------------------------------------

    def _get_grouped_servers(self) -> List[Dict[str, Any]]:
        """
        Группирует серверы по адресу (host, port).
        Каждая группа содержит host, port, name, и список users: List[Dict].
        """
        recents = self.config_mgr.get_recent_servers()
        saved = self.config_mgr.get_servers()

        groups: Dict[Tuple[str, int], Dict[str, Any]] = {}

        # 1. Недавние серверы
        for s in recents:
            host = s.get("host", "").strip()
            if not host:
                continue
            port = int(s.get("port", 22))
            key = (host, port)

            if key not in groups:
                groups[key] = {
                    "host": host,
                    "port": port,
                    "name": s.get("name") or host,
                    "users": []
                }

            user_list = groups[key]["users"]
            uname = s.get("username", "root")
            if not any(u.get("username") == uname for u in user_list):
                user_list.append(dict(s))

        # 2. Закладки серверов
        for s in saved:
            host = s.get("host", "").strip()
            if not host:
                continue
            port = int(s.get("port", 22))
            key = (host, port)

            if key not in groups:
                groups[key] = {
                    "host": host,
                    "port": port,
                    "name": s.get("name") or host,
                    "users": []
                }

            user_list = groups[key]["users"]
            uname = s.get("username", "root")
            if not any(u.get("username") == uname for u in user_list):
                user_list.append(dict(s))

        return list(groups.values())

    def _refresh_recent_servers_list(self):
        """Отрисовывает список серверов в левой панели."""
        for w in self.server_list_inner.winfo_children():
            w.destroy()

        c = self.theme_mgr.colors
        query = self.entry_server_search.get().strip().lower()

        # 1. Закреплённый сервер: Учебная песочница
        if not query or "демо" in query or "demo" in query or "песочница" in query:
            self._render_pinned_demo_item()

        # 2. Группированные серверы
        groups = self._get_grouped_servers()
        if query:
            filtered_groups = []
            for g in groups:
                match_host = query in g.get("host", "").lower()
                match_name = query in g.get("name", "").lower()
                match_user = any(query in u.get("username", "").lower() for u in g.get("users", []))
                if match_host or match_name or match_user:
                    filtered_groups.append(g)
            groups = filtered_groups

        if groups:
            lbl_sect = ttk.Label(
                self.server_list_inner,
                text="  СОХРАНЁННЫЕ СЕРВЕРЫ",
                font=(self.theme_mgr.ui_font, 8, "bold"),
                foreground=c["fg_muted"]
            )
            lbl_sect.pack(fill="x", pady=(8, 4), padx=6)

            for grp in groups:
                self._render_server_group_item(grp)
        elif not query:
            empty_box = ttk.Frame(self.server_list_inner, style="Card.TFrame", padding=14)
            empty_box.pack(fill="x", pady=16)
            ttk.Label(
                empty_box,
                text="Список серверов пуст\n\nНажмите «+ Добавить сервер», чтобы подключиться.",
                style="Dim.TLabel",
                wraplength=260,
                justify="center"
            ).pack(anchor="center")

    def _render_pinned_demo_item(self):
        """Отрисовывает карточку локальной демо-песочницы."""
        c = self.theme_mgr.colors

        item_frame = tk.Frame(
            self.server_list_inner,
            bg=c["surface_bg"],
            cursor="hand2",
            padx=10,
            pady=8
        )
        item_frame.pack(fill="x", pady=2, padx=4)

        tag_lbl = tk.Label(
            item_frame,
            text="DEMO",
            font=(self.theme_mgr.ui_font, 8, "bold"),
            bg=c["surface_hover"],
            fg=c["accent"],
            padx=5,
            pady=2
        )
        tag_lbl.pack(side="left", padx=(0, 10))

        text_box = tk.Frame(item_frame, bg=c["surface_bg"])
        text_box.pack(side="left", fill="both", expand=True)

        lbl_t = tk.Label(
            text_box,
            text="Демо-песочница",
            font=(self.theme_mgr.ui_font, 10, "bold"),
            fg=c["fg_bright"],
            bg=c["surface_bg"],
            anchor="w"
        )
        lbl_t.pack(fill="x")

        lbl_sub = tk.Label(
            text_box,
            text="Локальный сервер для тестов",
            font=(self.theme_mgr.ui_font, 8),
            fg=c["fg_dim"],
            bg=c["surface_bg"],
            anchor="w"
        )
        lbl_sub.pack(fill="x")

        btn_go = tk.Button(
            item_frame,
            text="Запустить",
            font=(self.theme_mgr.ui_font, 9),
            bg=c["card_bg"],
            fg=c["fg"],
            activebackground=c["surface_hover"],
            activeforeground=c["fg_bright"],
            relief="flat",
            borderwidth=1,
            highlightthickness=0,
            cursor="hand2",
            padx=8,
            pady=3,
            command=self._start_demo_server
        )
        btn_go.pack(side="right", padx=(4, 0))

        def on_enter(e):
            item_frame.config(bg=c["surface_hover"])
            text_box.config(bg=c["surface_hover"])
            lbl_t.config(bg=c["surface_hover"])
            lbl_sub.config(bg=c["surface_hover"])

        def on_leave(e):
            item_frame.config(bg=c["surface_bg"])
            text_box.config(bg=c["surface_bg"])
            lbl_t.config(bg=c["surface_bg"])
            lbl_sub.config(bg=c["surface_bg"])

        for w in (item_frame, tag_lbl, text_box, lbl_t, lbl_sub):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", lambda e: self._start_demo_server())

    def _render_server_group_item(self, grp: Dict[str, Any]):
        """Отрисовывает сервер в списке с поддержкой 1-клика и мульти-пользователей."""
        c = self.theme_mgr.colors
        users = grp.get("users", [])
        num_users = len(users)

        item_frame = tk.Frame(
            self.server_list_inner,
            bg=c["surface_bg"],
            cursor="hand2",
            padx=10,
            pady=8
        )
        item_frame.pack(fill="x", pady=2, padx=4)

        dot_lbl = tk.Label(
            item_frame,
            text="●",
            font=(self.theme_mgr.ui_font, 9),
            bg=c["surface_bg"],
            fg=c["accent_green"],
            padx=2
        )
        dot_lbl.pack(side="left", padx=(0, 8))

        text_box = tk.Frame(item_frame, bg=c["surface_bg"])
        text_box.pack(side="left", fill="both", expand=True)

        title = f"{grp['host']}:{grp['port']}"
        lbl_t = tk.Label(
            text_box,
            text=title,
            font=(self.theme_mgr.ui_font, 10, "bold"),
            fg=c["fg_bright"],
            bg=c["surface_bg"],
            anchor="w"
        )
        lbl_t.pack(fill="x")

        if num_users <= 1:
            u_name = users[0].get("username", "root") if users else "root"
            sub_text = u_name
        else:
            names = ", ".join(u.get("username", "") for u in users[:2])
            sub_text = f"{num_users} аккаунта: {names}"

        lbl_sub = tk.Label(
            text_box,
            text=sub_text,
            font=(self.theme_mgr.ui_font, 8),
            fg=c["fg_dim"],
            bg=c["surface_bg"],
            anchor="w"
        )
        lbl_sub.pack(fill="x")

        # Кнопка действия справа
        if num_users <= 1 and users:
            btn_action = tk.Button(
                item_frame,
                text="Войти",
                font=(self.theme_mgr.ui_font, 9),
                bg=c["card_bg"],
                fg=c["fg"],
                activebackground=c["surface_hover"],
                activeforeground=c["fg_bright"],
                relief="flat",
                borderwidth=1,
                highlightthickness=0,
                cursor="hand2",
                padx=10,
                pady=3,
                command=lambda srv=users[0]: self._connect_to_server_dict(srv)
            )
            btn_action.pack(side="right", padx=(4, 0))
        else:
            btn_action = tk.Button(
                item_frame,
                text="Выбрать ▼",
                font=(self.theme_mgr.ui_font, 8),
                bg=c["card_bg"],
                fg=c["fg"],
                activebackground=c["surface_hover"],
                activeforeground=c["fg_bright"],
                relief="flat",
                borderwidth=1,
                highlightthickness=0,
                cursor="hand2",
                padx=8,
                pady=3,
                command=lambda g=grp: self._open_user_picker_for_group(g)
            )
            btn_action.pack(side="right", padx=(4, 0))

        def on_enter(e):
            item_frame.config(bg=c["surface_hover"])
            dot_lbl.config(bg=c["surface_hover"])
            text_box.config(bg=c["surface_hover"])
            lbl_t.config(bg=c["surface_hover"])
            lbl_sub.config(bg=c["surface_hover"])

        def on_leave(e):
            item_frame.config(bg=c["surface_bg"])
            dot_lbl.config(bg=c["surface_bg"])
            text_box.config(bg=c["surface_bg"])
            lbl_t.config(bg=c["surface_bg"])
            lbl_sub.config(bg=c["surface_bg"])

        def on_item_click(e):
            if num_users <= 1 and users:
                self._connect_to_server_dict(users[0])
            else:
                self._open_user_picker_for_group(grp)

        for w in (item_frame, dot_lbl, text_box, lbl_t, lbl_sub):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_item_click)

    # -----------------------------------------------------------------
    # ПРАВАЯ ПАНЕЛЬ 1: Выбор пользователя для сервера (Мульти-вход)
    # -----------------------------------------------------------------

    def _build_user_picker_pane(self):
        c = self.theme_mgr.colors

        # Шапка
        header = ttk.Frame(self.pane_user_picker, style="Card.TFrame")
        header.pack(fill="x", pady=(0, 16))

        title_box = ttk.Frame(header, style="Card.TFrame")
        title_box.pack(side="left", fill="both", expand=True)

        self.lbl_picker_title = ttk.Label(
            title_box,
            text="",
            font=(self.theme_mgr.display_font, 14, "bold")
        )
        self.lbl_picker_title.pack(anchor="w")

        self.lbl_picker_subtitle = ttk.Label(
            title_box,
            text="Выберите пользователя для подключения к серверу",
            style="Subtitle.TLabel"
        )
        self.lbl_picker_subtitle.pack(anchor="w", pady=(2, 0))

        # Контейнер списка пользователей для этого сервера
        self.users_picker_container = ttk.Frame(self.pane_user_picker, style="Card.TFrame")
        self.users_picker_container.pack(fill="both", expand=True, pady=(0, 14))

        # Нижняя панель действий
        bottom_box = ttk.Frame(self.pane_user_picker, style="Card.TFrame")
        bottom_box.pack(fill="x")

        self.btn_picker_add_user = ttk.Button(
            bottom_box,
            text="+ Войти под другим пользователем",
            style="TButton",
            command=self._on_picker_add_other_user
        )
        self.btn_picker_add_user.pack(side="left")

    def _open_user_picker_for_group(self, grp: Dict[str, Any]):
        """Отображает выбор пользователя для сервера с несколькими аккаунтами."""
        self.active_server_group = grp
        c = self.theme_mgr.colors

        self.lbl_picker_title.config(text=f"Сервер: {grp['host']}:{grp['port']}")
        self.lbl_picker_subtitle.config(text=f"Сохранённые учётные записи ({len(grp.get('users', []))}):")

        for w in self.users_picker_container.winfo_children():
            w.destroy()

        users = grp.get("users", [])
        for u in users:
            row = tk.Frame(
                self.users_picker_container,
                bg=c["surface_bg"],
                cursor="hand2",
                padx=14,
                pady=10
            )
            row.pack(fill="x", pady=4)

            # Точка статуса
            dot = tk.Label(
                row,
                text="●",
                font=(self.theme_mgr.ui_font, 9),
                bg=c["surface_bg"],
                fg=c["accent"],
                padx=2
            )
            dot.pack(side="left", padx=(0, 10))

            # Текст
            t_box = tk.Frame(row, bg=c["surface_bg"])
            t_box.pack(side="left", fill="both", expand=True)

            u_name = u.get("username", "root")
            auth_name = "Вход по SSH-ключу" if u.get("auth_type") == "key" else "Вход по паролю"
            folder = u.get("initial_remote_path") or "/"

            lbl_u = tk.Label(
                t_box,
                text=u_name,
                font=(self.theme_mgr.ui_font, 10, "bold"),
                fg=c["fg_bright"],
                bg=c["surface_bg"],
                anchor="w"
            )
            lbl_u.pack(fill="x")

            lbl_sub = tk.Label(
                t_box,
                text=f"{auth_name}   •   Папка: {folder}",
                font=(self.theme_mgr.ui_font, 8),
                fg=c["fg_dim"],
                bg=c["surface_bg"],
                anchor="w"
            )
            lbl_sub.pack(fill="x")

            # Кнопка входа
            btn_in = tk.Button(
                row,
                text="Войти",
                font=(self.theme_mgr.ui_font, 9, "bold"),
                bg=c["accent"],
                fg=c["accent_text"],
                activebackground=c["accent_hover"],
                activeforeground=c["accent_text"],
                relief="flat",
                borderwidth=0,
                cursor="hand2",
                padx=14,
                pady=5,
                command=lambda srv=u: self._connect_to_server_dict(srv)
            )
            btn_in.pack(side="right")

            def on_enter(e, r=row, d=dot, tb=t_box, lu=lbl_u, ls=lbl_sub):
                r.config(bg=c["surface_hover"])
                d.config(bg=c["surface_hover"])
                tb.config(bg=c["surface_hover"])
                lu.config(bg=c["surface_hover"])
                ls.config(bg=c["surface_hover"])

            def on_leave(e, r=row, d=dot, tb=t_box, lu=lbl_u, ls=lbl_sub):
                r.config(bg=c["surface_bg"])
                d.config(bg=c["surface_bg"])
                tb.config(bg=c["surface_bg"])
                lu.config(bg=c["surface_bg"])
                ls.config(bg=c["surface_bg"])

            def on_row_click(e, srv=u):
                self._connect_to_server_dict(srv)

            for item_w in (row, dot, t_box, lbl_u, lbl_sub):
                item_w.bind("<Enter>", on_enter)
                item_w.bind("<Leave>", on_leave)
                item_w.bind("<Button-1>", on_row_click)

        # Переключаем правую панель на User Picker
        self.pane_new_connection.pack_forget()
        self.pane_user_picker.pack(fill="both", expand=True)

    def _on_picker_add_other_user(self):
        """Открывает форму подключения с уже заполненным хостом и портом для нового пользователя."""
        if self.active_server_group:
            host = self.active_server_group.get("host", "")
            port = str(self.active_server_group.get("port", 22))
            self._show_new_connection_form()
            self.entry_host.delete(0, tk.END)
            self.entry_host.insert(0, host)
            self.entry_port.delete(0, tk.END)
            self.entry_port.insert(0, port)
            self.entry_user.delete(0, tk.END)
            self.entry_user.focus_set()
        else:
            self._show_new_connection_form()

    # -----------------------------------------------------------------
    # ПРАВАЯ ПАНЕЛЬ 2: Форма добавления нового сервера
    # -----------------------------------------------------------------

    def _build_new_connection_pane(self):
        c = self.theme_mgr.colors

        header = ttk.Frame(self.pane_new_connection, style="Card.TFrame")
        header.pack(fill="x", pady=(0, 10))

        ttk.Label(
            header,
            text="Новое подключение",
            font=(self.theme_mgr.display_font, 13, "bold")
        ).pack(anchor="w")

        ttk.Label(
            header,
            text="Введите реквизиты сервера или вставьте их из буфера обмена",
            style="Subtitle.TLabel"
        ).pack(anchor="w", pady=(2, 0))

        # Умная вставка из буфера
        paste_card = ttk.Frame(self.pane_new_connection, style="Surface.TFrame", padding=10)
        paste_card.pack(fill="x", pady=(0, 10))

        btn_paste = ttk.Button(
            paste_card,
            text="Вставить из буфера обмена",
            style="TButton",
            command=self._on_smart_paste
        )
        btn_paste.pack(fill="x", pady=(0, 4))

        self.lbl_paste_status = ttk.Label(
            paste_card,
            text="Поддерживаются реквизиты AmneziaVPN, SFTP-ссылки (sftp://) и письма хостинга",
            style="Dim.TLabel",
            background=c["surface_bg"]
        )
        self.lbl_paste_status.pack(anchor="w")

        # Поля ввода
        form_grid = ttk.Frame(self.pane_new_connection, style="Card.TFrame")
        form_grid.pack(fill="x", pady=2)

        # 1. Хост и Порт
        ttk.Label(form_grid, text="Хост (IP или домен):", style="FieldLabel.TLabel").grid(row=0, column=0, sticky="w", pady=(2, 2))
        ttk.Label(form_grid, text="Порт:", style="FieldLabel.TLabel").grid(row=0, column=1, sticky="w", padx=(12, 0), pady=(2, 2))

        self.entry_host = ttk.Entry(form_grid, font=(self.theme_mgr.ui_font, 10))
        self.entry_host.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.entry_host.bind("<Return>", lambda e: self._on_connect_click())

        self.entry_port = ttk.Entry(form_grid, font=(self.theme_mgr.mono_font, 10), width=8)
        self.entry_port.grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(0, 6))
        self.entry_port.insert(0, "22")
        self.entry_port.bind("<Return>", lambda e: self._on_connect_click())

        form_grid.columnconfigure(0, weight=1)

        # 2. Логин
        ttk.Label(form_grid, text="Имя пользователя:", style="FieldLabel.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 2))
        self.entry_user = ttk.Entry(form_grid, font=(self.theme_mgr.ui_font, 10))
        self.entry_user.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.entry_user.insert(0, "root")
        self.entry_user.bind("<Return>", lambda e: self._on_connect_click())

        # 3. Авторизация
        auth_switch_bar = ttk.Frame(form_grid, style="Card.TFrame")
        auth_switch_bar.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(2, 4))

        self.lbl_auth = ttk.Label(auth_switch_bar, text="Авторизация: Пароль", style="FieldLabel.TLabel")
        self.lbl_auth.pack(side="left")

        self.btn_toggle_auth = ttk.Button(
            auth_switch_bar,
            text="Использовать SSH-ключ",
            style="Tool.TButton",
            command=self._toggle_auth_type
        )
        self.btn_toggle_auth.pack(side="right")

        self.pass_container = ttk.Frame(form_grid, style="Card.TFrame")
        self.pass_container.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        self.entry_pass = ttk.Entry(self.pass_container, font=(self.theme_mgr.ui_font, 10), show="●")
        self.entry_pass.pack(side="left", fill="x", expand=True)
        self.entry_pass.bind("<Return>", lambda e: self._on_connect_click())

        self.btn_eye = ttk.Button(self.pass_container, text="Показать", style="Tool.TButton", command=self._toggle_show_password)
        self.btn_eye.pack(side="right", padx=(6, 0))

        self.key_container = ttk.Frame(form_grid, style="Card.TFrame")
        self.lbl_key_file = ttk.Label(self.key_container, text="Ключ не выбран", style="Dim.TLabel")
        self.lbl_key_file.pack(side="left", fill="x", expand=True)
        btn_browse_key = ttk.Button(self.key_container, text="Выбрать ключ...", style="Tool.TButton", command=self._browse_key)
        btn_browse_key.pack(side="right")

        # 4. Начальная папка
        ttk.Label(form_grid, text="Папка на сервере (опционально):", style="FieldLabel.TLabel").grid(row=6, column=0, columnspan=2, sticky="w", pady=(2, 2))
        self.entry_initial_folder = ttk.Entry(form_grid, font=(self.theme_mgr.mono_font, 9))
        self.entry_initial_folder.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        folder_pills = ttk.Frame(form_grid, style="Card.TFrame")
        folder_pills.grid(row=8, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(folder_pills, text="Быстрый выбор:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        for p_name, p_val in [("Авто", ""), ("Домой (~)", "~"), ("Корень (/)", "/"), ("/upload", "/upload"), ("/var/www/html", "/var/www/html")]:
            ttk.Button(folder_pills, text=p_name, style="Pill.TButton", command=lambda v=p_val: self._set_initial_folder(v)).pack(side="left", padx=2)

        # Главная кнопка подключения
        self.btn_connect = ttk.Button(
            self.pane_new_connection,
            text="Подключиться к серверу",
            style="Primary.TButton",
            command=self._on_connect_click
        )
        self.btn_connect.pack(fill="x", pady=(2, 6))

        self.lbl_connect_status = ttk.Label(self.pane_new_connection, text="", style="Status.TLabel")
        self.lbl_connect_status.pack(anchor="center")

    def _show_new_connection_form(self):
        """Отображает форму добавления сервера в правой области."""
        self.pane_user_picker.pack_forget()
        self.pane_new_connection.pack(fill="both", expand=True)
        self.entry_host.focus_set()

    # -----------------------------------------------------------------
    # Обработчики авторизации и буфера
    # -----------------------------------------------------------------

    def _toggle_show_password(self):
        if self.entry_pass.cget("show") == "":
            self.entry_pass.config(show="●")
            self.btn_eye.config(text="Показать")
        else:
            self.entry_pass.config(show="")
            self.btn_eye.config(text="Скрыть")

    def _toggle_auth_type(self):
        if self.auth_mode == "password":
            self.auth_mode = "key"
            self.lbl_auth.config(text="Авторизация: SSH-ключ")
            self.pass_container.grid_remove()
            self.key_container.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 6))
            self.btn_toggle_auth.config(text="Использовать пароль")
            if not self.selected_key_path:
                self._browse_key()
        else:
            self.auth_mode = "password"
            self.lbl_auth.config(text="Авторизация: Пароль")
            self.key_container.grid_remove()
            self.pass_container.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 6))
            self.btn_toggle_auth.config(text="Использовать SSH-ключ")

    def _browse_key(self):
        f = filedialog.askopenfilename(
            parent=self.root,
            title="Выберите приватный SSH-ключ",
            filetypes=[("Ключи SSH (*.pem, *.key, id_*)", "*.*")]
        )
        if f:
            self.selected_key_path = f
            self.lbl_key_file.config(text=os.path.basename(f))

    def _on_smart_paste(self):
        try:
            cb_text = self.root.clipboard_get()
        except Exception:
            self.lbl_paste_status.config(
                text="Буфер обмена пуст",
                foreground=self.theme_mgr.colors["accent_amber"]
            )
            return

        parsed = parse_sftp_clipboard(cb_text)
        if not parsed:
            self.lbl_paste_status.config(
                text="Не удалось распознать реквизиты в буфере",
                foreground=self.theme_mgr.colors["accent_amber"]
            )
            return

        if "host" in parsed:
            self.entry_host.delete(0, tk.END)
            self.entry_host.insert(0, parsed["host"])

        if "port" in parsed:
            self.entry_port.delete(0, tk.END)
            self.entry_port.insert(0, parsed["port"])

        if "username" in parsed:
            self.entry_user.delete(0, tk.END)
            self.entry_user.insert(0, parsed["username"])

        if "password" in parsed:
            if self.auth_mode != "password":
                self._toggle_auth_type()
            self.entry_pass.delete(0, tk.END)
            self.entry_pass.insert(0, parsed["password"])

        if "folder" in parsed:
            self._set_initial_folder(parsed["folder"])
        elif parsed.get("username") == "sftp_user":
            self._set_initial_folder("/sftp_user")

        self.lbl_paste_status.config(
            text="Настройки сервера успешно вставлены",
            foreground=self.theme_mgr.colors["accent_green"]
        )

    def _set_initial_folder(self, val: str):
        self.entry_initial_folder.delete(0, tk.END)
        self.entry_initial_folder.insert(0, val)

    def _connect_to_server_dict(self, s: Dict[str, Any]):
        """Мгновенное подключение к переданному серверу в 1 клик."""
        self._show_new_connection_form()
        self.entry_host.delete(0, tk.END)
        self.entry_host.insert(0, s["host"])
        self.entry_port.delete(0, tk.END)
        self.entry_port.insert(0, str(s.get("port", 22)))
        self.entry_user.delete(0, tk.END)
        self.entry_user.insert(0, s.get("username", "root"))

        if s.get("auth_type") == "key":
            if self.auth_mode != "key":
                self._toggle_auth_type()
            self.selected_key_path = s.get("key_path", "")
            self.lbl_key_file.config(text=os.path.basename(self.selected_key_path))
        else:
            if self.auth_mode != "password":
                self._toggle_auth_type()
            self.entry_pass.delete(0, tk.END)
            self.entry_pass.insert(0, s.get("password", ""))

        self._on_connect_click()

    # -----------------------------------------------------------------
    # ЭКРАН 2: Чистый проводник файлов на сервере
    # -----------------------------------------------------------------

    def _build_files_screen(self):
        c = self.theme_mgr.colors
        self.frame_files = ttk.Frame(self.main_container, style="Main.TFrame")

        # 1. Навигация и адресная строка
        nav_card = ttk.Frame(self.frame_files, style="Card.TFrame", padding=(12, 6))
        nav_card.pack(fill="x", padx=12, pady=(8, 4))

        btn_back = ttk.Button(nav_card, text="← Назад", style="Tool.TButton", command=self._remote_go_up)
        btn_back.pack(side="left", padx=(0, 4))

        btn_up = ttk.Button(nav_card, text="↑ Вверх", style="Tool.TButton", command=self._remote_go_up)
        btn_up.pack(side="left", padx=(0, 4))

        btn_home = ttk.Button(nav_card, text="Домой", style="Tool.TButton", command=lambda: self._refresh_remote_files("~"))
        btn_home.pack(side="left", padx=(0, 8))

        ttk.Label(nav_card, text="Путь:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.entry_remote_path = ttk.Entry(nav_card, font=(self.theme_mgr.mono_font, 10))
        self.entry_remote_path.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_remote_path.bind("<Return>", lambda e: self._remote_go_path())

        btn_copy_path = ttk.Button(nav_card, text="Копировать", style="Tool.TButton", command=self._copy_current_path)
        btn_copy_path.pack(side="left", padx=(0, 4))

        btn_refresh = ttk.Button(nav_card, text="Обновить", style="Tool.TButton", command=self._refresh_remote_files)
        btn_refresh.pack(side="left")

        # 2. Панель действий над файлами и поиск (без обрезания текста!)
        actions_bar = ttk.Frame(self.frame_files, style="Card.TFrame", padding=(12, 6))
        actions_bar.pack(fill="x", padx=12, pady=(0, 4))

        left_act = ttk.Frame(actions_bar, style="Card.TFrame")
        left_act.pack(side="left")

        btn_upload = ttk.Button(
            left_act,
            text="Загрузить",
            style="Primary.TButton",
            command=self._upload_files_dialog
        )
        btn_upload.pack(side="left", padx=(0, 4))

        btn_mkdir = ttk.Button(
            left_act,
            text="Новая папка",
            style="TButton",
            command=self._create_remote_folder_dialog
        )
        btn_mkdir.pack(side="left", padx=(0, 4))

        self.btn_download_sel = ttk.Button(
            left_act,
            text="Скачать",
            style="TButton",
            command=self._download_selected_items
        )
        self.btn_download_sel.pack(side="left", padx=(0, 4))

        self.btn_rename_sel = ttk.Button(
            left_act,
            text="Переименовать",
            style="TButton",
            command=self._rename_selected_item
        )
        self.btn_rename_sel.pack(side="left", padx=(0, 4))

        self.btn_edit_sel = ttk.Button(
            left_act,
            text="Редактировать",
            style="TButton",
            command=self._edit_selected_file
        )
        self.btn_edit_sel.pack(side="left", padx=(0, 4))

        self.btn_chmod_sel = ttk.Button(
            left_act,
            text="Права (chmod)",
            style="TButton",
            command=self._chmod_selected_item
        )
        self.btn_chmod_sel.pack(side="left", padx=(0, 4))

        self.btn_delete_sel = ttk.Button(
            left_act,
            text="Удалить",
            style="Danger.TButton",
            command=self._delete_selected_items
        )
        self.btn_delete_sel.pack(side="left")

        # Поиск
        search_box = ttk.Frame(actions_bar, style="Card.TFrame")
        search_box.pack(side="right")

        ttk.Label(search_box, text="Поиск:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.entry_search = ttk.Entry(search_box, font=(self.theme_mgr.ui_font, 9), width=20)
        self.entry_search.pack(side="left", padx=(0, 4))
        self.entry_search.bind("<KeyRelease>", lambda e: self._filter_remote_items())

        btn_clear_search = ttk.Button(search_box, text="✕", style="Tool.TButton", command=self._clear_search)
        btn_clear_search.pack(side="left", padx=(0, 6))

        self.lbl_search_count = ttk.Label(search_box, text="", style="Badge.TLabel")
        self.lbl_search_count.pack(side="left")

        # 3. Таблица файлов
        table_container = ttk.Frame(self.frame_files, style="Card.TFrame", padding=2)
        table_container.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        columns = ("name", "size", "type", "mode", "mtime")
        self.tree_remote = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="extended")

        self.tree_remote.heading("name", text="Имя", anchor="w", command=lambda: self._sort_column("name"))
        self.tree_remote.heading("size", text="Размер", anchor="e", command=lambda: self._sort_column("size"))
        self.tree_remote.heading("type", text="Тип", anchor="w", command=lambda: self._sort_column("type"))
        self.tree_remote.heading("mode", text="Права", anchor="center", command=lambda: self._sort_column("mode"))
        self.tree_remote.heading("mtime", text="Изменён", anchor="center", command=lambda: self._sort_column("mtime"))

        self.tree_remote.column("name", width=380, minwidth=180, anchor="w")
        self.tree_remote.column("size", width=110, minwidth=80, anchor="e")
        self.tree_remote.column("type", width=160, minwidth=110, anchor="w")
        self.tree_remote.column("mode", width=100, minwidth=80, anchor="center")
        self.tree_remote.column("mtime", width=150, minwidth=120, anchor="center")

        scroll_y = ttk.Scrollbar(table_container, orient="vertical", command=self.tree_remote.yview)
        self.tree_remote.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")
        self.tree_remote.pack(fill="both", expand=True)

        self.tree_remote.bind("<Double-1>", self._on_remote_item_double_click)
        self.tree_remote.bind("<Return>", self._on_remote_item_double_click)
        self.tree_remote.bind("<<TreeviewSelect>>", self._on_item_select_change)
        self.tree_remote.bind("<Button-3>", self._show_context_menu)
        self.tree_remote.bind("<Delete>", lambda e: self._delete_selected_items())
        self.tree_remote.bind("<BackSpace>", lambda e: self._remote_go_up())
        self.tree_remote.bind("<F5>", lambda e: self._refresh_remote_files())
        self.tree_remote.bind("<F2>", lambda e: self._rename_selected_item())
        self.tree_remote.bind("<Control-a>", self._select_all_items)

        # 4. Прогресс передачи
        self.progress_container = ttk.Frame(self.frame_files, style="Card.TFrame", padding=(12, 6))

        self.lbl_transfer_status = ttk.Label(self.progress_container, text="", font=(self.theme_mgr.ui_font, 9, "bold"))
        self.lbl_transfer_status.pack(side="left")

        self.btn_cancel_transfer = ttk.Button(
            self.progress_container,
            text="Отмена",
            style="Danger.TButton",
            command=self._cancel_active_task
        )

        self.progressbar = ttk.Progressbar(self.progress_container, style="Horizontal.TProgressbar", mode="determinate")

        # 5. Нижняя строка
        self.footer_bar = ttk.Frame(self.frame_files, style="Main.TFrame", padding=(12, 4))
        self.footer_bar.pack(fill="x", padx=12, pady=(0, 4))

        self.lbl_selected_info = ttk.Label(self.footer_bar, text="Готово к работе", style="Status.TLabel")
        self.lbl_selected_info.pack(side="left")

        self.lbl_footer_right = ttk.Label(self.footer_bar, text="Enter: Открыть  •  F2: Переименовать  •  F5: Обновить  •  Del: Удалить", style="Status.TLabel")
        self.lbl_footer_right.pack(side="right")

        self._build_context_menu()

    def _build_context_menu(self):
        c = self.theme_mgr.colors
        self.menu = tk.Menu(self.root, tearoff=0, bg=c["card_bg"], fg=c["fg"], activebackground=c["accent"], activeforeground="#ffffff")
        self.menu.add_command(label="Скачать на компьютер", command=self._download_selected_items)
        self.menu.add_command(label="Редактировать", command=self._edit_selected_file)
        self.menu.add_separator()
        self.menu.add_command(label="Переименовать", command=self._rename_selected_item)
        self.menu.add_command(label="Права доступа (chmod)", command=self._chmod_selected_item)
        self.menu.add_command(label="Скопировать путь", command=self._copy_selected_path)
        self.menu.add_separator()
        self.menu.add_command(label="Удалить", command=self._delete_selected_items)

    def _show_context_menu(self, event):
        item_id = self.tree_remote.identify_row(event.y)
        if item_id:
            if item_id not in self.tree_remote.selection():
                self.tree_remote.selection_set(item_id)
        if self.tree_remote.selection():
            self.menu.post(event.x_root, event.y_root)

    # -----------------------------------------------------------------
    # Сортировка колонок
    # -----------------------------------------------------------------

    def _sort_column(self, col: str):
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False

        headers = {
            "name": "Имя",
            "size": "Размер",
            "type": "Тип",
            "mode": "Права",
            "mtime": "Изменён"
        }
        for c_id, text in headers.items():
            if c_id == self.sort_column:
                arrow = " ▼" if self.sort_reverse else " ▲"
                self.tree_remote.heading(c_id, text=f"{text}{arrow}")
            else:
                self.tree_remote.heading(c_id, text=text)

        def sort_key(it: FileItem):
            is_folder = not it.is_dir
            if col == "size":
                return (is_folder, it.size or 0)
            elif col == "mtime":
                return (is_folder, it.mtime or 0)
            elif col == "type":
                return (is_folder, it.type_desc.lower())
            elif col == "mode":
                return (is_folder, it.permissions_octal)
            else:
                return (is_folder, it.name.lower())

        self.filtered_remote_items.sort(key=sort_key, reverse=self.sort_reverse)
        self._render_tree()

    # -----------------------------------------------------------------
    # Фоновые задачи и подключение
    # -----------------------------------------------------------------

    def _run_in_background(self, target, on_success=None, on_error=None, description=""):
        def worker():
            try:
                res = target()
                self.work_queue.put(("success", on_success, res, description))
            except Exception as e:
                self.work_queue.put(("error", on_error, e, description))

        th = threading.Thread(target=worker, daemon=True)
        th.start()

    def _process_queue(self):
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return

        while not self.work_queue.empty():
            try:
                kind, callback, data, desc = self.work_queue.get_nowait()
            except queue.Empty:
                break

            self._hide_progressbar()

            if kind == "success":
                if callback:
                    callback(data)
            elif kind == "error":
                if callback:
                    callback(data)
                else:
                    messagebox.showerror("Ошибка операции", str(data), parent=self.root)

        try:
            if self.root.winfo_exists():
                self._schedule_queue_process()
        except Exception:
            pass

    def _on_connect_click(self):
        host = self.entry_host.get().strip()
        if not host:
            messagebox.showwarning("Внимание", "Пожалуйста, укажите хост сервера (IP-адрес или домен)!", parent=self.root)
            self.entry_host.focus_set()
            return

        try:
            port = int(self.entry_port.get().strip() or "22")
        except ValueError:
            port = 22

        username = self.entry_user.get().strip() or "root"
        password = self.entry_pass.get() if self.auth_mode == "password" else None
        key_filename = self.selected_key_path if self.auth_mode == "key" else None
        initial_dir = self.entry_initial_folder.get().strip() or None

        self.active_client = self.real_sftp
        self.btn_connect.config(text="Подключение к серверу...", state="disabled")
        self.lbl_connect_status.config(text="Устанавливаем защищённое соединение...", foreground=self.theme_mgr.colors["accent_sky"])

        def do_connect():
            return self.active_client.connect(
                host=host,
                port=port,
                username=username,
                password=password,
                key_filename=key_filename,
                initial_dir=initial_dir
            )

        def on_success(initial_path):
            self.btn_connect.config(text="Подключиться к серверу", state="normal")
            self.lbl_connect_status.config(text="")

            self.config_mgr.add_recent_server(
                host=host,
                port=port,
                username=username,
                password=password if password else "",
                auth_type=self.auth_mode,
                key_path=self.selected_key_path
            )
            self._save_last_connection()
            self._show_screen("files")
            self._refresh_remote_files(initial_path)

        def on_error(e):
            self.btn_connect.config(text="Подключиться к серверу", state="normal")
            self.lbl_connect_status.config(text=f"Ошибка: {e}", foreground=self.theme_mgr.colors["accent_red"])
            messagebox.showerror("Не удалось подключиться", str(e), parent=self.root)

        self._run_in_background(do_connect, on_success, on_error, "Подключение")

    def _disconnect(self):
        if self.active_client:
            self.active_client.disconnect()
        self._show_screen("connect")

    def _start_demo_server(self, show_dialog: bool = False):
        self.active_client = self.demo_sftp
        self.active_client.connect()
        self._show_screen("files")
        self._refresh_remote_files("/")

        if show_dialog:
            messagebox.showinfo(
                "Учебный режим (Песочница)",
                "Вы успешно подключены к локальной песочнице EasySFTP.\n\n"
                "Здесь можно безопасно тренироваться:\n"
                "• Создавать изолированных пользователей (кнопка «Пользователи»)\n"
                "• Редактировать код прямо на сервере (двойной клик по файлу)\n"
                "• Скачивать и загружать файлы (кнопки «Загрузить» и «Скачать»)",
                parent=self.root
            )

    def _open_user_manager(self):
        is_demo = (self.active_client == self.demo_sftp)
        mgr = ServerUserManager(self.active_client, is_demo=is_demo)

        available_dirs = ["/"]
        for it in self.current_remote_items:
            if it.is_dir:
                available_dirs.append(it.path)

        UserManagerWindow(
            self.root,
            server_user_mgr=mgr,
            theme_mgr=self.theme_mgr,
            current_server_host=self.active_client.current_host,
            current_server_port=self.active_client.current_port,
            server_directories=available_dirs
        )

    # -----------------------------------------------------------------
    # Файловые операции
    # -----------------------------------------------------------------

    def _refresh_remote_files(self, target_path: Optional[str] = None):
        if not self.active_client.is_connected():
            return

        def do_list():
            if target_path:
                self.active_client.cd(target_path)
            pwd = self.active_client.pwd()
            items = self.active_client.list_dir(pwd)
            return pwd, items

        def on_success(data):
            pwd, items = data
            self.entry_remote_path.delete(0, tk.END)
            self.entry_remote_path.insert(0, pwd)
            self.current_remote_items = items
            self._filter_remote_items()

        def on_error(e):
            err_str = str(e)
            if "permission" in err_str.lower() or "отказано в доступе" in err_str.lower():
                user = getattr(self.active_client, "current_user", "sftp_user")
                ans = messagebox.askyesno(
                    "Доступ к папке ограничен",
                    f"{err_str}\n\n"
                    f"Корень сервера '/' защищён от обычных пользователей.\n"
                    f"Перейти в рабочую папку пользователя '/{user}'?",
                    parent=self.root
                )
                if ans:
                    for target_fallback in [f"/{user}", ".", "/upload", "/data"]:
                        try:
                            self.active_client.cd(target_fallback)
                            self._refresh_remote_files()
                            return
                        except Exception:
                            continue
            messagebox.showerror("Ошибка доступа", err_str, parent=self.root)

        self._run_in_background(do_list, on_success, on_error=on_error, description="Обновление файлов")

    def _filter_remote_items(self):
        query = self.entry_search.get().strip().lower()
        if not query:
            self.filtered_remote_items = list(self.current_remote_items)
            self.lbl_search_count.config(text="")
        else:
            self.filtered_remote_items = [it for it in self.current_remote_items if query in it.name.lower()]
            self.lbl_search_count.config(text=f"Найдено: {len(self.filtered_remote_items)}")

        self._sort_column(self.sort_column)

    def _clear_search(self):
        self.entry_search.delete(0, tk.END)
        self._filter_remote_items()

    def _render_tree(self):
        c = self.theme_mgr.colors
        self.tree_remote.delete(*self.tree_remote.get_children())

        self.tree_remote.tag_configure("even", background=c["tree_bg"])
        self.tree_remote.tag_configure("odd", background=c["tree_alt_bg"])

        for i, it in enumerate(self.filtered_remote_items):
            tag = "odd" if i % 2 == 1 else "even"
            display_name = f"{it.icon}  {it.name}"
            self.tree_remote.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    display_name,
                    it.formatted_size,
                    it.type_desc,
                    it.permissions_octal,
                    it.formatted_time
                ),
                tags=(tag,)
            )

        self._on_item_select_change()

    def _get_selected_items(self) -> List[FileItem]:
        selected = []
        for sid in self.tree_remote.selection():
            try:
                idx = int(sid)
                if 0 <= idx < len(self.filtered_remote_items):
                    selected.append(self.filtered_remote_items[idx])
            except ValueError:
                pass
        return selected

    def _on_item_select_change(self, event=None):
        items = self._get_selected_items()
        total_folders = sum(1 for it in self.filtered_remote_items if it.is_dir)
        total_files = len(self.filtered_remote_items) - total_folders
        total_bytes = sum(it.size or 0 for it in self.filtered_remote_items if not it.is_dir)

        if not items:
            self.lbl_selected_info.config(
                text=f"Папок: {total_folders}, Файлов: {total_files} ({format_size(total_bytes)})"
            )
            self.btn_download_sel.config(state="disabled")
            self.btn_rename_sel.config(state="disabled")
            self.btn_edit_sel.config(state="disabled")
            self.btn_chmod_sel.config(state="disabled")
            self.btn_delete_sel.config(state="disabled")
        else:
            first = items[0]
            if len(items) == 1:
                self.lbl_selected_info.config(text=f"Выбрано: {first.name} ({first.formatted_size}) • {first.type_desc}")
                self.btn_download_sel.config(state="normal")
                self.btn_rename_sel.config(state="normal")
                self.btn_edit_sel.config(state="normal" if not first.is_dir else "disabled")
                self.btn_chmod_sel.config(state="normal")
                self.btn_delete_sel.config(state="normal")
            else:
                sel_bytes = sum(it.size or 0 for it in items if not it.is_dir)
                self.lbl_selected_info.config(text=f"Выбрано объектов: {len(items)} ({format_size(sel_bytes)})")
                self.btn_download_sel.config(state="normal")
                self.btn_rename_sel.config(state="disabled")
                self.btn_edit_sel.config(state="disabled")
                self.btn_chmod_sel.config(state="disabled")
                self.btn_delete_sel.config(state="normal")

    def _select_all_items(self, event=None):
        self.tree_remote.selection_set(self.tree_remote.get_children())
        return "break"

    def _on_remote_item_double_click(self, event=None):
        items = self._get_selected_items()
        if not items:
            return
        item = items[0]
        if item.is_dir:
            self._refresh_remote_files(item.path)
        else:
            if is_text_file(item.name):
                self._open_remote_editor(item)
            else:
                self._download_selected_items()

    def _remote_go_up(self):
        cur = self.active_client.pwd()
        parent = posixpath.dirname(cur.rstrip("/"))
        if not parent:
            parent = "/"
        self._refresh_remote_files(parent)

    def _remote_go_path(self):
        new_path = self.entry_remote_path.get().strip()
        if new_path:
            self._refresh_remote_files(new_path)

    def _copy_current_path(self):
        cur = self.entry_remote_path.get().strip()
        if cur:
            self.root.clipboard_clear()
            self.root.clipboard_append(cur)
            self.lbl_footer_right.config(text="Путь скопирован в буфер")
            self.root.after(2000, lambda: self.lbl_footer_right.config(text="Enter: Открыть  •  F5: Обновить  •  Del: Удалить"))

    def _copy_selected_path(self):
        items = self._get_selected_items()
        if items:
            self.root.clipboard_clear()
            self.root.clipboard_append(items[0].path)
            self.lbl_footer_right.config(text=f"Путь к '{items[0].name}' скопирован")
            self.root.after(2000, lambda: self.lbl_footer_right.config(text="Enter: Открыть  •  F5: Обновить  •  Del: Удалить"))

    def _show_progressbar(self, text: str):
        self.lbl_transfer_status.config(text=text)
        self.progressbar["value"] = 0
        self.progress_container.pack(fill="x", padx=12, pady=(0, 4), before=self.footer_bar)
        self.progressbar.pack(side="left", fill="x", expand=True, padx=8)
        self.btn_cancel_transfer.pack(side="right")

    def _hide_progressbar(self):
        self.progressbar.pack_forget()
        self.btn_cancel_transfer.pack_forget()
        self.progress_container.pack_forget()

    def _cancel_active_task(self):
        if self.cancel_token:
            self.cancel_token.cancel()
            self.lbl_transfer_status.config(text="Отмена операции...")

    def _upload_files_dialog(self):
        if not self.active_client.is_connected():
            return

        files = filedialog.askopenfilenames(
            parent=self.root,
            title="Выберите файлы для загрузки на сервер"
        )
        if not files:
            return

        remote_dir = self.active_client.pwd()
        self.cancel_token = CancelToken()
        self._show_progressbar(f"Загрузка файлов ({len(files)} шт.)...")

        def do_upload():
            for fpath in files:
                fname = os.path.basename(fpath)
                rem_path = posixpath.join(remote_dir, fname)
                self.active_client.upload_file(fpath, rem_path, self._on_transfer_progress, self.cancel_token)

        def on_success(_):
            self._refresh_remote_files()
            messagebox.showinfo("Успешно", f"Файлы ({len(files)} шт.) успешно загружены на сервер!", parent=self.root)

        self._run_in_background(do_upload, on_success, description="Загрузка на сервер")

    def _download_selected_items(self):
        items = self._get_selected_items()
        if not items:
            return

        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(downloads_dir):
            downloads_dir = os.path.expanduser("~")

        dest_dir = filedialog.askdirectory(
            parent=self.root,
            title="Куда сохранить файлы на вашем компьютере?",
            initialdir=downloads_dir
        )
        if not dest_dir:
            return

        self.cancel_token = CancelToken()
        self._show_progressbar(f"Скачивание объектов ({len(items)} шт.)...")

        def do_download():
            for it in items:
                loc_path = os.path.join(dest_dir, it.name)
                if it.is_dir:
                    self.active_client.download_directory_recursive(
                        it.path, loc_path, self._on_transfer_progress, self.cancel_token
                    )
                else:
                    self.active_client.download_file(
                        it.path, loc_path, self._on_transfer_progress, self.cancel_token
                    )

        def on_success(_):
            ans = messagebox.askyesno(
                "Успешно скачано",
                f"Файлы успешно сохранены в папку:\n{dest_dir}\n\nОткрыть эту папку в проводнике Windows?",
                parent=self.root
            )
            if ans:
                self.local_client.open_in_system(dest_dir)

        self._run_in_background(do_download, on_success, description="Скачивание с сервера")

    def _on_transfer_progress(self, transferred: int, total: int, speed: float, filename: str):
        pct = (transferred / total * 100) if total > 0 else 0
        speed_str = f"{format_size(int(speed))}/с"
        trans_str = format_size(transferred)
        tot_str = format_size(total)

        def update():
            self.progressbar["value"] = pct
            self.lbl_transfer_status.config(
                text=f"{filename}: {trans_str} из {tot_str} ({pct:.0f}%) • {speed_str}"
            )

        self.root.after(0, update)

    def _open_remote_editor(self, item: FileItem):
        def do_read():
            return self.active_client.read_text_file(item.path)

        def on_success(content):
            def on_save(new_text):
                self.active_client.write_text_file(item.path, new_text)

            EditorWindow(
                self.root,
                filename=item.name,
                initial_content=content,
                theme_mgr=self.theme_mgr,
                on_save=on_save,
                is_remote=True
            )

        self._run_in_background(do_read, on_success, description=f"Открытие {item.name}")

    def _edit_selected_file(self):
        items = self._get_selected_items()
        if items and not items[0].is_dir:
            self._open_remote_editor(items[0])

    def _delete_selected_items(self):
        items = self._get_selected_items()
        if not items:
            return

        names = ", ".join(f"'{it.name}'" for it in items[:3])
        if len(items) > 3:
            names += f" и ещё {len(items) - 3} шт."

        ans = messagebox.askyesno(
            "Удаление с сервера",
            f"Вы уверены, что хотите удалить с сервера:\n{names}?\n\nЭто действие нельзя отменить!",
            parent=self.root
        )
        if not ans:
            return

        def do_delete():
            for it in items:
                if it.is_dir:
                    self.active_client.delete_directory_recursive(it.path)
                else:
                    self.active_client.delete_file(it.path)

        def on_success(_):
            self._refresh_remote_files()

        self._run_in_background(do_delete, on_success, description="Удаление с сервера")

    def _create_remote_folder_dialog(self):
        name = simpledialog.askstring("Новая папка", "Введите имя новой папки на сервере:", parent=self.root)
        if name and name.strip():
            new_path = posixpath.join(self.active_client.pwd(), name.strip())

            def do_mkdir():
                self.active_client.create_directory(new_path)

            def on_success(_):
                self._refresh_remote_files()

            self._run_in_background(do_mkdir, on_success, description="Создание папки")

    def _on_f2_pressed(self, event=None):
        if hasattr(self, "frame_files") and self.frame_files.winfo_manager() == "pack":
            self._rename_selected_item()
            return "break"

    def _rename_selected_item(self, event=None):
        items = self._get_selected_items()
        if items:
            item = items[0]
            target_path = item.path.rstrip("/")
            is_folder = item.is_dir
            item_name = item.name
            parent_dir = posixpath.dirname(target_path)
            if not parent_dir:
                parent_dir = "/"
        else:
            target_path = self.active_client.pwd().rstrip("/")
            if not target_path or target_path == "/":
                messagebox.showinfo(
                    "Переименование",
                    "Выберите файл или папку в таблице для переименования.",
                    parent=self.root
                )
                return
            is_folder = True
            item_name = posixpath.basename(target_path)
            parent_dir = posixpath.dirname(target_path)
            if not parent_dir:
                parent_dir = "/"

        entity_type = "папку" if is_folder else "файл"
        new_name = simpledialog.askstring(
            f"Переименовать {entity_type}",
            f"Новое имя для {entity_type} '{item_name}':",
            initialvalue=item_name,
            parent=self.root
        )

        if not new_name:
            return

        clean_name = new_name.strip().strip("/\\")
        if not clean_name or clean_name == item_name:
            return

        new_path = posixpath.join(parent_dir, clean_name)

        def do_rename():
            self.active_client.rename(target_path, new_path)

        def on_success(_):
            self.set_status(f"Успешно переименовано: '{item_name}' → '{clean_name}'")
            if not items:
                self._refresh_remote_files(new_path)
            else:
                self._refresh_remote_files()

        self._run_in_background(do_rename, on_success, description="Переименование")

    def set_status(self, text: str):
        if hasattr(self, "lbl_selected_info"):
            self.lbl_selected_info.config(text=text)

    def _chmod_selected_item(self):
        items = self._get_selected_items()
        if not items:
            return
        item = items[0]

        def apply_chmod(mode: int, recursive: bool):
            def do_chmod():
                self.active_client.chmod(item.path, mode)

            def on_success(_):
                self._refresh_remote_files()

            self._run_in_background(do_chmod, on_success, description="Смена прав")

        PermissionsDialog(
            self.root,
            filename=item.name,
            initial_mode=item.mode,
            is_dir=item.is_dir,
            theme_mgr=self.theme_mgr,
            on_apply=apply_chmod
        )

    # -----------------------------------------------------------------
    # Вспомогательные окна
    # -----------------------------------------------------------------

    def _open_server_manager(self):
        def on_connect_server(s: Dict[str, Any]):
            self._connect_to_server_dict(s)

        ServerManagerDialog(self.root, self.config_mgr, self.theme_mgr, on_connect_server)

    def _open_help(self):
        HelpWindow(self.root, self.theme_mgr)

    def _toggle_theme(self):
        new_theme = self.theme_mgr.toggle_theme(self.root)
        self.config_mgr.set_setting("theme", new_theme)
        if self.active_client.is_connected():
            self._render_tree()
        else:
            self._refresh_recent_servers_list()
        return new_theme

    def _save_last_connection(self):
        self.config_mgr.set_last_connection(
            host=self.entry_host.get().strip(),
            port=int(self.entry_port.get().strip() or "22"),
            username=self.entry_user.get().strip(),
            auth_type=self.auth_mode,
            key_path=self.selected_key_path,
            password=self.entry_pass.get()
        )

    def _load_last_connection(self):
        last = self.config_mgr.get_last_connection()
        if last.get("host"):
            self.entry_host.delete(0, tk.END)
            self.entry_host.insert(0, last.get("host", ""))
            self.entry_port.delete(0, tk.END)
            self.entry_port.insert(0, str(last.get("port", 22)))
            self.entry_user.delete(0, tk.END)
            self.entry_user.insert(0, last.get("username", "root"))
            if last.get("auth_type") == "key" and last.get("key_path"):
                if self.auth_mode != "key":
                    self._toggle_auth_type()
                self.selected_key_path = last.get("key_path")
                self.lbl_key_file.config(text=os.path.basename(self.selected_key_path))
            else:
                self.entry_pass.delete(0, tk.END)
                self.entry_pass.insert(0, last.get("password", ""))

    def _on_close_app(self):
        try:
            if hasattr(self, "_queue_after_id") and self._queue_after_id:
                self.root.after_cancel(self._queue_after_id)
                self._queue_after_id = None
        except Exception:
            pass
        try:
            if self.active_client:
                self.active_client.disconnect()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
