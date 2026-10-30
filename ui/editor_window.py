"""
Встроенный профессиональный текстовый редактор и просмотрщик кода.
Поддерживает:
- Номера строк и активную строку
- Базовую подсветку синтаксиса (Python, HTML, CSS, JSON, Shell, конфиги)
- Поиск с подсветкой совпадений (Ctrl+F)
- Быстрое сохранение на сервер (Ctrl+S)
- Статусную строку с позицией курсора, размером и кодировкой
"""

from __future__ import annotations
import re
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

from ui.theme import ThemeManager


# Регулярные выражения для легковесной подсветки синтаксиса
SYNTAX_PATTERNS = {
    "keyword": r'\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|lambda|yield|async|await|None|True|False|function|const|let|var|switch|case|break|continue)\b',
    "string": r'(".*?"|\'.*?\'|`.*?`)',
    "comment": r'(#.*?$|//.*?$|/\*.*?\*/|<!--.*?-->)',
    "number": r'\b\d+(\.\d+)?\b',
}


class TextLineNumbers(tk.Canvas):
    """Боковая панель для отображения номеров строк с привязкой к теме."""
    def __init__(self, parent, text_widget: tk.Text, theme_mgr: ThemeManager, **kwargs):
        super().__init__(parent, **kwargs)
        self.text_widget = text_widget
        self.theme_mgr = theme_mgr
        self.configure(width=48, highlightthickness=0)

    def redraw(self, *args):
        c = self.theme_mgr.colors
        self.delete("all")
        self.configure(bg=c["surface_bg"])

        i = self.text_widget.index("@0,0")
        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(
                40, y + 2,
                anchor="ne",
                text=linenum,
                fill=c["fg_muted"],
                font=(self.theme_mgr.mono_font, 9)
            )
            i = self.text_widget.index(f"{i}+1line")


class CustomText(tk.Text):
    """Текстовое поле с отслеживанием прокрутки и изменений для номеров строк."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig = self._w + "_orig"
        self.tk.call("rename", self._w, self._orig)
        self.tk.createcommand(self._w, self._cmd)

    def _cmd(self, *args):
        cmd = (self._orig,) + args
        result = None
        try:
            result = self.tk.call(cmd)
        except Exception:
            return result

        if args[0] in ("insert", "delete") or args[0:3] == ("mark", "set", "insert") or args[0:2] == ("yview", "moveto") or args[0:2] == ("yview", "scroll"):
            self.event_generate("<<Change>>", when="tail")

        return result


class EditorWindow(tk.Toplevel):
    """
    Окно встроенного профессионального редактора файлов.
    """
    def __init__(
        self,
        parent: tk.Tk,
        filename: str,
        initial_content: str,
        theme_mgr: ThemeManager,
        on_save: Optional[Callable[[str], None]] = None,
        is_remote: bool = True
    ):
        super().__init__(parent)
        self.filename = filename
        self.theme_mgr = theme_mgr
        self.on_save = on_save
        self.is_remote = is_remote
        self.is_modified = False

        location_tag = "Удалённый сервер" if is_remote else "Локальный файл"
        self.title(f"Редактор: {filename} — {location_tag}")
        self.geometry("920x640")
        self.minsize(680, 460)

        self.transient(parent)
        self._center_window(parent)

        self._build_ui(initial_content)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center_window(self, parent):
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() - 920) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - 640) // 2
            self.geometry(f"+{max(20, x)}+{max(20, y)}")
        except Exception:
            pass

    def _build_ui(self, initial_content: str):
        c = self.theme_mgr.colors
        self.configure(bg=c["bg"])

        # 1. Верхняя панель управления (Toolbar)
        toolbar = ttk.Frame(self, style="Card.TFrame", padding=(14, 10))
        toolbar.pack(fill="x", padx=12, pady=(12, 6))

        # Левая часть тулбара: значок и кнопка Сохранить
        left_tb = ttk.Frame(toolbar, style="Card.TFrame")
        left_tb.pack(side="left")

        lbl_file = ttk.Label(
            left_tb,
            text=self.filename,
            font=(self.theme_mgr.display_font, 11, "bold")
        )
        lbl_file.pack(side="left", padx=(0, 14))

        self.btn_save = ttk.Button(
            left_tb,
            text="Сохранить",
            style="Primary.TButton",
            command=self._save
        )
        self.btn_save.pack(side="left", padx=(0, 8))

        # Панель быстрого поиска
        search_frame = ttk.Frame(toolbar, style="Card.TFrame")
        search_frame.pack(side="left", padx=14)

        ttk.Label(search_frame, text="Поиск:", style="Dim.TLabel").pack(side="left", padx=(0, 4))
        self.entry_find = ttk.Entry(search_frame, width=18)
        self.entry_find.pack(side="left", padx=(0, 4))
        self.entry_find.bind("<Return>", lambda e: self._find_next())

        btn_next = ttk.Button(search_frame, text="▶", width=3, style="Tool.TButton", command=self._find_next)
        btn_next.pack(side="left", padx=2)

        self.lbl_find_info = ttk.Label(search_frame, text="", style="Dim.TLabel")
        self.lbl_find_info.pack(side="left", padx=6)

        # Правая часть тулбара: статус изменений
        self.lbl_mod_status = ttk.Label(
            toolbar,
            text="● Без изменений",
            style="Dim.TLabel",
            font=(self.theme_mgr.ui_font, 9, "bold")
        )
        self.lbl_mod_status.pack(side="right", padx=6)

        # 2. Основной редактор (номера строк + текстовое поле)
        editor_card = ttk.Frame(self, style="Card.TFrame", padding=2)
        editor_card.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        self.text = CustomText(
            editor_card,
            wrap="none",
            undo=True,
            font=(self.theme_mgr.mono_font, 10),
            bg=c["card_bg"],
            fg=c["fg"],
            insertbackground=c["fg_bright"],
            selectbackground=c["accent"],
            selectforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=8
        )

        self.line_numbers = TextLineNumbers(editor_card, self.text, self.theme_mgr)
        self.line_numbers.pack(side="left", fill="y")

        scroll_y = ttk.Scrollbar(editor_card, orient="vertical", command=self._on_scroll_y)
        self.text.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side="right", fill="y")

        scroll_x = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(xscrollcommand=scroll_x.set)
        scroll_x.pack(fill="x", padx=12, pady=(0, 4))

        self.text.pack(side="left", fill="both", expand=True)

        # Теги подсветки
        self._configure_syntax_tags()

        # 3. Нижняя статусная панель
        status_box = ttk.Frame(self, style="Main.TFrame", padding=(12, 4))
        status_box.pack(fill="x", padx=12, pady=(0, 8))

        self.status_bar = ttk.Label(
            status_box,
            text="Строка 1, Колонка 1   |   UTF-8   |   0 символов",
            style="Status.TLabel"
        )
        self.status_bar.pack(side="left")

        lbl_hints = ttk.Label(
            status_box,
            text="Горячие клавиши: Ctrl+S (Сохранить), Ctrl+F (Поиск), Ctrl+Z (Отмена)",
            style="Status.TLabel"
        )
        lbl_hints.pack(side="right")

        # Заполнение начальным текстом
        self.text.insert("1.0", initial_content)
        self.text.edit_reset()
        self._apply_syntax_highlight()

        # События
        self.text.bind("<<Change>>", self._on_text_change)
        self.text.bind("<KeyRelease>", self._update_cursor_pos)
        self.text.bind("<ButtonRelease-1>", self._update_cursor_pos)
        self.bind("<Control-s>", lambda e: (self._save(), "break")[1])
        self.bind("<Control-f>", lambda e: (self.entry_find.focus_set(), "break")[1])
        self.bind("<Escape>", lambda e: self._on_close())

        self.text.bind("<MouseWheel>", lambda e: self.after(10, self.line_numbers.redraw))
        self.line_numbers.redraw()

    def _configure_syntax_tags(self):
        c = self.theme_mgr.colors
        is_dark = (self.theme_mgr.theme_name == "dark")

        kw_color = "#818cf8" if is_dark else "#4338ca"
        str_color = "#34d399" if is_dark else "#059669"
        com_color = "#64748b" if is_dark else "#94a3b8"
        num_color = "#f59e0b" if is_dark else "#d97706"

        self.text.tag_configure("syntax_kw", foreground=kw_color, font=(self.theme_mgr.mono_font, 10, "bold"))
        self.text.tag_configure("syntax_str", foreground=str_color)
        self.text.tag_configure("syntax_com", foreground=com_color, font=(self.theme_mgr.mono_font, 10, "italic"))
        self.text.tag_configure("syntax_num", foreground=num_color)
        self.text.tag_configure("search_match", background=c["accent_amber"], foreground="#000000")

    def _apply_syntax_highlight(self):
        """Легковесная подсветка синтаксиса для популярных файлов."""
        content = self.text.get("1.0", "end-1c")
        if len(content) > 100000:
            # Для очень больших файлов не применяем подсветку во избежание подвисаний
            return

        for tag in ("syntax_kw", "syntax_str", "syntax_com", "syntax_num"):
            self.text.tag_remove(tag, "1.0", tk.END)

        for match in re.finditer(SYNTAX_PATTERNS["comment"], content, re.MULTILINE):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.text.tag_add("syntax_com", start, end)

        for match in re.finditer(SYNTAX_PATTERNS["string"], content):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.text.tag_add("syntax_str", start, end)

        for match in re.finditer(SYNTAX_PATTERNS["keyword"], content):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.text.tag_add("syntax_kw", start, end)

        for match in re.finditer(SYNTAX_PATTERNS["number"], content):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.text.tag_add("syntax_num", start, end)

    def _on_scroll_y(self, *args):
        self.text.yview(*args)
        self.line_numbers.redraw()

    def _on_text_change(self, event=None):
        self.line_numbers.redraw()
        if not self.is_modified:
            self.is_modified = True
            self.title(f"* Редактор: {self.filename} (есть несохранённые изменения)")
            self.lbl_mod_status.config(text="● Не сохранён", foreground=self.theme_mgr.colors["accent_amber"])

    def _update_cursor_pos(self, event=None):
        try:
            line, col = self.text.index("insert").split(".")
            total_lines = self.text.index("end-1c").split(".")[0]
            total_chars = len(self.text.get("1.0", "end-1c"))
            self.status_bar.config(
                text=f"Строка {line} из {total_lines}, Колонка {int(col) + 1}   |   UTF-8   |   {total_chars} симв."
            )
        except Exception:
            pass

    def _find_next(self):
        query = self.entry_find.get()
        if not query:
            return

        self.text.tag_remove("search_match", "1.0", tk.END)
        start_pos = self.text.index("insert")
        pos = self.text.search(query, start_pos, stopindex=tk.END, nocase=True)
        if not pos:
            pos = self.text.search(query, "1.0", stopindex=start_pos, nocase=True)

        if pos:
            end_pos = f"{pos}+{len(query)}c"
            self.text.tag_add("search_match", pos, end_pos)
            self.text.mark_set("insert", end_pos)
            self.text.see(pos)
            self.lbl_find_info.config(text="Найдено")
        else:
            self.lbl_find_info.config(text="Не найдено")

    def _save(self):
        content = self.text.get("1.0", "end-1c")
        if self.on_save:
            try:
                self.on_save(content)
                self.is_modified = False
                location_tag = "Удалённый сервер" if self.is_remote else "Локальный файл"
                self.title(f"Редактор: {self.filename} — {location_tag}")
                self.lbl_mod_status.config(text="● Сохранено", foreground=self.theme_mgr.colors["accent_green"])
            except Exception as e:
                messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить файл:\n{e}", parent=self)

    def _on_close(self):
        if self.is_modified:
            ans = messagebox.askyesnocancel(
                "Несохранённые изменения",
                f"В файле '{self.filename}' есть несохранённые изменения.\nСохранить перед закрытием?",
                parent=self
            )
            if ans is True:
                self._save()
                self.destroy()
            elif ans is False:
                self.destroy()
        else:
            self.destroy()
