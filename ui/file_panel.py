"""
Компонент файловой панели (FilePanel) для отображения локальных и удалённых файлов.
Поддерживает поиск в реальном времени, сортировку по колонкам, контекстное меню и горячие клавиши.
"""

from __future__ import annotations
import os
import posixpath
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Callable, List, Optional, Any

from core.file_utils import FileItem, format_size
from ui.theme import ThemeManager


class FilePanel(ttk.Frame):
    """
    Универсальная панель проводника (для локального компьютера или SFTP сервера).
    """
    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        is_remote: bool,
        theme_mgr: ThemeManager,
        on_navigate: Optional[Callable[[str], None]] = None,
        on_action: Optional[Callable[[str, List[FileItem]], None]] = None,
        **kwargs
    ):
        super().__init__(parent, style="Card.TFrame", **kwargs)
        self.title_text = title
        self.is_remote = is_remote
        self.theme_mgr = theme_mgr
        self.on_navigate = on_navigate
        self.on_action = on_action

        self.current_path = "/" if is_remote else os.path.expanduser("~")
        self.items: List[FileItem] = []
        self.filtered_items: List[FileItem] = []
        self.sort_column = "name"
        self.sort_reverse = False

        self._build_ui()

    def _build_ui(self):
        c = self.theme_mgr.colors

        # Верхняя панель: Заголовок и кнопки навигации
        top_bar = ttk.Frame(self, style="Card.TFrame")
        top_bar.pack(fill="x", padx=10, pady=(10, 4))

        self.lbl_title = ttk.Label(
            top_bar,
            text=self.title_text,
            font=(self.theme_mgr.display_font, 11, "bold")
        )
        self.lbl_title.pack(side="left")

        # Кнопки быстрых действий в шапке
        btn_box = ttk.Frame(top_bar, style="Card.TFrame")
        btn_box.pack(side="right")

        self.btn_up = ttk.Button(btn_box, text="↑ Вверх", width=8, style="Tool.TButton", command=self._on_click_up)
        self.btn_up.pack(side="left", padx=2)

        self.btn_home = ttk.Button(btn_box, text="Домой", width=7, style="Tool.TButton", command=self._on_click_home)
        self.btn_home.pack(side="left", padx=2)

        self.btn_mkdir = ttk.Button(btn_box, text="+ Папка", width=8, style="Tool.TButton", command=self._on_click_mkdir)
        self.btn_mkdir.pack(side="left", padx=2)

        self.btn_refresh = ttk.Button(btn_box, text="Обновить", width=9, style="Tool.TButton", command=self._on_click_refresh)
        self.btn_refresh.pack(side="left", padx=2)

        # Строка пути
        path_box = ttk.Frame(self, style="Card.TFrame")
        path_box.pack(fill="x", padx=10, pady=3)

        ttk.Label(path_box, text="Путь:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.entry_path = ttk.Entry(path_box, font=(self.theme_mgr.mono_font, 9))
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.entry_path.bind("<Return>", lambda e: self._on_submit_path())

        btn_go = ttk.Button(path_box, text="Перейти", width=8, style="Tool.TButton", command=self._on_submit_path)
        btn_go.pack(side="right")

        # Строка быстрого поиска
        search_box = ttk.Frame(self, style="Card.TFrame")
        search_box.pack(fill="x", padx=10, pady=(2, 6))

        ttk.Label(search_box, text="Поиск:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.entry_search = ttk.Entry(search_box, font=(self.theme_mgr.ui_font, 9))
        self.entry_search.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.entry_search.bind("<KeyRelease>", lambda e: self._filter_items())

        btn_clear_search = ttk.Button(search_box, text="✕", width=3, style="Tool.TButton", command=self._clear_search)
        btn_clear_search.pack(side="right")

        # Таблица файлов (Treeview)
        tree_frame = ttk.Frame(self, style="Card.TFrame")
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        extra_col = "Права" if self.is_remote else "Тип"
        columns = ("name", "size", "mtime", "extra")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="extended"
        )

        self.tree.heading("name", text="Имя файла / папки", anchor="w", command=lambda: self._sort_by("name"))
        self.tree.heading("size", text="Размер", anchor="e", command=lambda: self._sort_by("size"))
        self.tree.heading("mtime", text="Изменён", anchor="center", command=lambda: self._sort_by("mtime"))
        self.tree.heading("extra", text=extra_col, anchor="w", command=lambda: self._sort_by("extra"))

        self.tree.column("name", width=240, minwidth=140, anchor="w")
        self.tree.column("size", width=85, minwidth=60, anchor="e")
        self.tree.column("mtime", width=125, minwidth=100, anchor="center")
        self.tree.column("extra", width=95, minwidth=70, anchor="w")

        # Скроллбары
        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")

        scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=scroll_x.set)
        scroll_x.pack(side="bottom", fill="x")

        self.tree.pack(side="left", fill="both", expand=True)

        # Нижняя информационная строка
        self.lbl_status = ttk.Label(
            self,
            text="Готово к работе",
            style="Dim.TLabel"
        )
        self.lbl_status.pack(fill="x", padx=10, pady=(2, 6))

        # Привязка событий
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", self._on_double_click)
        self.tree.bind("<BackSpace>", lambda e: self._on_click_up())
        self.tree.bind("<Delete>", lambda e: self._trigger_action("delete"))
        self.tree.bind("<F2>", lambda e: self._trigger_action("rename"))
        self.tree.bind("<F5>", lambda e: self._on_click_refresh())
        self.tree.bind("<Control-a>", self._on_select_all)
        self.tree.bind("<Button-3>", self._show_context_menu)

        # Контекстное меню
        self._build_context_menu()

    def _build_context_menu(self):
        c = self.theme_mgr.colors
        self.menu = tk.Menu(self, tearoff=0, bg=c["card_bg"], fg=c["fg"], activebackground=c["accent"], activeforeground="#ffffff")

        primary_action_title = "Скачать на компьютер" if self.is_remote else "Загрузить на сервер"
        self.menu.add_command(label=primary_action_title, command=lambda: self._trigger_action("transfer"))
        self.menu.add_separator()
        self.menu.add_command(label="Редактировать", command=lambda: self._trigger_action("edit"))
        if not self.is_remote:
            self.menu.add_command(label="Открыть в проводнике", command=lambda: self._trigger_action("open_system"))
        self.menu.add_command(label="Переименовать", command=lambda: self._trigger_action("rename"))
        if self.is_remote:
            self.menu.add_command(label="Права доступа (chmod)", command=lambda: self._trigger_action("chmod"))
        self.menu.add_separator()
        self.menu.add_command(label="Удалить", command=lambda: self._trigger_action("delete"))

    def _show_context_menu(self, event):
        item_id = self.tree.identify_row(event.y)
        if item_id:
            if item_id not in self.tree.selection():
                self.tree.selection_set(item_id)
        if self.tree.selection():
            self.menu.post(event.x_root, event.y_root)

    def set_items(self, current_path: str, items: List[FileItem]):
        self.current_path = current_path
        self.entry_path.delete(0, tk.END)
        self.entry_path.insert(0, current_path)
        self.items = list(items)
        self._filter_items()

    def _clear_search(self):
        self.entry_search.delete(0, tk.END)
        self._filter_items()

    def _filter_items(self):
        q = self.entry_search.get().strip().lower()
        if not q:
            self.filtered_items = list(self.items)
        else:
            self.filtered_items = [it for it in self.items if q in it.name.lower()]

        self._sort_current_items()
        self._render()

    def _sort_by(self, col: str):
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        self._sort_current_items()
        self._render()

    def _sort_current_items(self):
        def key_func(it: FileItem):
            is_folder = not it.is_dir
            if self.sort_column == "size":
                return (is_folder, it.size or 0)
            elif self.sort_column == "mtime":
                return (is_folder, it.mtime or 0)
            elif self.sort_column == "extra":
                extra_val = it.permissions_octal if self.is_remote else it.type_desc
                return (is_folder, extra_val)
            else:
                return (is_folder, it.name.lower())

        self.filtered_items.sort(key=key_func, reverse=self.sort_reverse)

    def _render(self):
        c = self.theme_mgr.colors
        self.tree.delete(*self.tree.get_children())

        self.tree.tag_configure("even", background=c["tree_bg"])
        self.tree.tag_configure("odd", background=c["tree_alt_bg"])

        for i, it in enumerate(self.filtered_items):
            extra = it.permissions_octal if self.is_remote else it.type_desc
            tag = "odd" if i % 2 == 1 else "even"
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(f"{it.icon} {it.name}", it.formatted_size, it.formatted_time, extra),
                tags=(tag,)
            )

        total_files = len(self.filtered_items)
        total_bytes = sum(it.size or 0 for it in self.filtered_items if not it.is_dir)
        self.lbl_status.config(text=f"Объектов: {total_files} ({format_size(total_bytes)})")

    def get_selected_items(self) -> List[FileItem]:
        selected = []
        for sid in self.tree.selection():
            try:
                idx = int(sid)
                if 0 <= idx < len(self.filtered_items):
                    selected.append(self.filtered_items[idx])
            except ValueError:
                pass
        return selected

    def _on_select_all(self, event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _on_double_click(self, event=None):
        sel = self.get_selected_items()
        if not sel:
            return
        item = sel[0]
        if item.is_dir:
            if self.on_navigate:
                self.on_navigate(item.path)
        else:
            self._trigger_action("transfer")

    def _on_click_up(self):
        if self.is_remote:
            parent = posixpath.dirname(self.current_path.rstrip("/"))
            if not parent:
                parent = "/"
        else:
            parent = os.path.dirname(self.current_path)
            if not parent:
                parent = self.current_path

        if self.on_navigate:
            self.on_navigate(parent)

    def _on_click_home(self):
        home_path = "/" if self.is_remote else os.path.expanduser("~")
        if self.on_navigate:
            self.on_navigate(home_path)

    def _on_click_refresh(self):
        if self.on_navigate:
            self.on_navigate(self.current_path)

    def _on_click_mkdir(self):
        name = simpledialog.askstring("Новая папка", "Введите имя новой папки:", parent=self)
        if name and name.strip():
            self._trigger_action("mkdir", extra_data=name.strip())

    def _on_submit_path(self):
        path = self.entry_path.get().strip()
        if path and self.on_navigate:
            self.on_navigate(path)

    def _trigger_action(self, action_name: str, extra_data: Any = None):
        if not self.on_action:
            return
        items = self.get_selected_items()
        if extra_data:
            self.on_action(action_name, (items, extra_data))
        else:
            self.on_action(action_name, items)
