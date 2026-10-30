"""
Темизация и визуальное оформление EasySFTP.
Профессиональный современный дизайн в стиле Windows 11 Fluent & Deep Slate.
Поддержка High-DPI экранов высокой чёткости и динамической смены светлой/тёмной темы.
"""

from __future__ import annotations
import sys
import tkinter as tk
from tkinter import ttk, font as tkfont
from typing import Dict, Tuple, Any


def enable_high_dpi():
    """Включает чёткие шрифты без размытия на экранах высокой чёткости Windows (High-DPI)."""
    if sys.platform == "win32":
        try:
            import ctypes
            # Попытка установить Per-Monitor DPI Awareness V2 (2) или V1 (1)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try:
                    import ctypes
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass


# Палитра современного минималистичного дизайна (Minimalist Slate & Clean Light)
THEMES: Dict[str, Dict[str, str]] = {
    "dark": {
        "name": "dark",
        "bg": "#121316",               # Сдержанный тёмный матовый фон (Obsidian Slate)
        "card_bg": "#18191f",          # Панели и карточки с мягкой глубиной
        "surface_bg": "#21232b",       # Инпуты, списки и второстепенные поверхности
        "surface_hover": "#2b2e38",    # Аккуратный эффект наведения
        "surface_active": "#353844",   # Нажатие
        "fg": "#f3f4f6",               # Чистый основной текст
        "fg_dim": "#9ca3af",           # Второстепенный текст (Zinc 400)
        "fg_muted": "#6b7280",         # Приглушённые подсказки
        "fg_bright": "#ffffff",        # Высококонтрастный текст
        "border": "#262934",           # Тонкие границы карточек (Hairline border)
        "border_light": "#363a49",     # Выделенная рамка
        "accent": "#6366f1",           # Лаконичный акцентный индиго (Linear style)
        "accent_hover": "#4f46e5",     # Тёмный индиго
        "accent_text": "#ffffff",
        "accent_green": "#10b981",     # Спокойный изумрудный
        "accent_green_hover": "#059669",
        "accent_red": "#f43f5e",       # Сдержанный коралловый
        "accent_red_hover": "#e11d48",
        "accent_amber": "#f59e0b",     # Янтарный
        "accent_sky": "#38bdf8",       # Небесный
        "tree_bg": "#18191f",
        "tree_fg": "#f3f4f6",
        "tree_sel_bg": "#2e3446",      # Минималистичное мягкое выделение
        "tree_sel_fg": "#ffffff",
        "tree_alt_bg": "#15161b",      # Мягкое чередование строк
        "header_bg": "#1c1e26",
        "header_fg": "#cbd5e1",
        "entry_bg": "#1a1c24",
        "entry_fg": "#ffffff",
        "entry_border": "#2c303d",
        "badge_bg": "#222533",
        "badge_fg": "#818cf8",
    },
    "light": {
        "name": "light",
        "bg": "#f8f9fa",               # Чистый светлый минималистичный фон
        "card_bg": "#ffffff",          # Белые поверхности карточек
        "surface_bg": "#f1f3f5",       # Мягкие нейтральные серые плашки
        "surface_hover": "#e9ecef",    # Наведение
        "surface_active": "#dee2e6",   # Нажатие
        "fg": "#111827",               # Глубокий тёмный текст (Gray 900)
        "fg_dim": "#4b5563",           # Второстепенный текст (Gray 600)
        "fg_muted": "#9ca3af",         # Приглушённый текст
        "fg_bright": "#000000",
        "border": "#e5e7eb",           # Тонкая рамка (Gray 200)
        "border_light": "#d1d5db",
        "accent": "#4f46e5",           # Индиго
        "accent_hover": "#4338ca",
        "accent_text": "#ffffff",
        "accent_green": "#059669",     # Изумрудный
        "accent_green_hover": "#047857",
        "accent_red": "#e11d48",       # Красный
        "accent_red_hover": "#be123c",
        "accent_amber": "#d97706",     # Янтарный
        "accent_sky": "#0284c7",
        "tree_bg": "#ffffff",
        "tree_fg": "#111827",
        "tree_sel_bg": "#e0e7ff",      # Мягкое пастельное выделение
        "tree_sel_fg": "#1e1b4b",
        "tree_alt_bg": "#f9fafb",
        "header_bg": "#f3f4f6",
        "header_fg": "#374151",
        "entry_bg": "#ffffff",
        "entry_fg": "#111827",
        "entry_border": "#d1d5db",
        "badge_bg": "#eef2ff",
        "badge_fg": "#4338ca",
    }
}


def get_system_font_names() -> Tuple[str, str, str]:
    """
    Определяет наилучшие доступные современные шрифты в операционной системе.
    Возвращает (UI_FONT, DISPLAY_FONT, MONO_FONT).
    """
    try:
        available = set(tkfont.families())
    except Exception:
        available = set()

    # Основной шрифт интерфейса (Windows 11 / Windows 10)
    if "Segoe UI Variable Text" in available:
        ui_font = "Segoe UI Variable Text"
    elif "Segoe UI" in available:
        ui_font = "Segoe UI"
    elif "SF Pro Display" in available:
        ui_font = "SF Pro Display"
    elif "Inter" in available:
        ui_font = "Inter"
    else:
        ui_font = "Arial"

    # Шрифт заголовков
    if "Segoe UI Variable Display" in available:
        display_font = "Segoe UI Variable Display"
    elif "Segoe UI" in available:
        display_font = "Segoe UI"
    else:
        display_font = ui_font

    # Моноширинный шрифт (для кода, редактора, путей и размеров)
    if "Cascadia Code" in available:
        mono_font = "Cascadia Code"
    elif "Cascadia Mono" in available:
        mono_font = "Cascadia Mono"
    elif "Consolas" in available:
        mono_font = "Consolas"
    elif "Menlo" in available:
        mono_font = "Menlo"
    else:
        mono_font = "Courier New"

    return ui_font, display_font, mono_font


class ThemeManager:
    """
    Управляет текущей цветовой темой, шрифтами и стилями ttk.
    """
    def __init__(self, theme_name: str = "dark"):
        self.theme_name = theme_name if theme_name in THEMES else "dark"
        self.colors = THEMES[self.theme_name]
        self.ui_font, self.display_font, self.mono_font = get_system_font_names()

    def set_theme(self, theme_name: str, root: tk.Tk):
        if theme_name in THEMES:
            self.theme_name = theme_name
            self.colors = THEMES[theme_name]
            self.apply(root)

    def toggle_theme(self, root: tk.Tk) -> str:
        new_theme = "light" if self.theme_name == "dark" else "dark"
        self.set_theme(new_theme, root)
        return new_theme

    def apply(self, root: tk.Tk):
        """
        Применяет современную стилизацию ко всем элементам приложения.
        """
        c = self.colors
        root.configure(bg=c["bg"])

        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        ui_f = self.ui_font
        disp_f = self.display_font
        mono_f = self.mono_font

        # -----------------------------------------------------------------
        # Фреймы и контейнеры
        # -----------------------------------------------------------------
        style.configure("TFrame", background=c["bg"])
        style.configure("Main.TFrame", background=c["bg"])
        style.configure("Card.TFrame", background=c["card_bg"], relief="flat")
        style.configure("Surface.TFrame", background=c["surface_bg"], relief="flat")
        style.configure("Toolbar.TFrame", background=c["card_bg"], relief="flat")
        style.configure("Sidebar.TFrame", background=c["card_bg"], relief="flat")

        # -----------------------------------------------------------------
        # Текстовые метки (TLabel)
        # -----------------------------------------------------------------
        style.configure(
            "TLabel",
            background=c["card_bg"],
            foreground=c["fg"],
            font=(ui_f, 10)
        )
        style.configure(
            "Main.TLabel",
            background=c["bg"],
            foreground=c["fg"],
            font=(ui_f, 10)
        )
        style.configure(
            "Title.TLabel",
            background=c["card_bg"],
            foreground=c["fg_bright"],
            font=(disp_f, 13, "bold")
        )
        style.configure(
            "Header.TLabel",
            background=c["card_bg"],
            foreground=c["fg_bright"],
            font=(disp_f, 16, "bold")
        )
        style.configure(
            "Subtitle.TLabel",
            background=c["card_bg"],
            foreground=c["fg_dim"],
            font=(ui_f, 9)
        )
        style.configure(
            "Dim.TLabel",
            background=c["card_bg"],
            foreground=c["fg_dim"],
            font=(ui_f, 9)
        )
        style.configure(
            "Status.TLabel",
            background=c["bg"],
            foreground=c["fg_dim"],
            font=(ui_f, 9)
        )
        style.configure(
            "FieldLabel.TLabel",
            background=c["card_bg"],
            foreground=c["fg_dim"],
            font=(ui_f, 9, "bold")
        )
        style.configure(
            "Badge.TLabel",
            background=c["badge_bg"],
            foreground=c["badge_fg"],
            font=(ui_f, 8, "bold"),
            padding=(6, 2)
        )
        style.configure(
            "Mono.TLabel",
            background=c["card_bg"],
            foreground=c["fg"],
            font=(mono_f, 9)
        )

        # -----------------------------------------------------------------
        # Таблица файлов (Treeview)
        # -----------------------------------------------------------------
        style.configure(
            "Treeview",
            background=c["tree_bg"],
            foreground=c["tree_fg"],
            fieldbackground=c["tree_bg"],
            bordercolor=c["border"],
            borderwidth=1,
            rowheight=34,
            font=(ui_f, 9)
        )
        style.map(
            "Treeview",
            background=[("selected", c["tree_sel_bg"])],
            foreground=[("selected", c["tree_sel_fg"])]
        )

        style.configure(
            "Treeview.Heading",
            background=c["header_bg"],
            foreground=c["header_fg"],
            relief="flat",
            font=(ui_f, 9, "bold"),
            padding=(10, 7),
            bordercolor=c["border"]
        )
        style.map(
            "Treeview.Heading",
            background=[("active", c["surface_hover"])],
            foreground=[("active", c["fg_bright"])]
        )

        # -----------------------------------------------------------------
        # Кнопки (TButton)
        # -----------------------------------------------------------------
        # Стандартная кнопка (Вторичная / Минималистичный контур)
        style.configure(
            "TButton",
            background=c["surface_bg"],
            foreground=c["fg"],
            borderwidth=1,
            bordercolor=c["border"],
            lightcolor=c["surface_bg"],
            darkcolor=c["surface_bg"],
            focuscolor="none",
            relief="flat",
            font=(ui_f, 9),
            padding=(10, 5)
        )
        style.map(
            "TButton",
            background=[("active", c["surface_hover"]), ("pressed", c["surface_active"])],
            foreground=[("active", c["fg_bright"])],
            bordercolor=[("active", c["border_light"])]
        )

        # Главная кнопка действия (Vibrant Minimal Accent)
        style.configure(
            "Primary.TButton",
            background=c["accent"],
            foreground=c["accent_text"],
            borderwidth=0,
            focuscolor="none",
            relief="flat",
            font=(ui_f, 9, "bold"),
            padding=(12, 6)
        )
        style.map(
            "Primary.TButton",
            background=[("active", c["accent_hover"]), ("pressed", c["accent_hover"])],
            foreground=[("active", c["accent_text"])]
        )

        # Кнопка Успеха / Подключения (Чистый Emerald)
        style.configure(
            "Success.TButton",
            background=c["accent_green"],
            foreground="#ffffff",
            borderwidth=0,
            focuscolor="none",
            relief="flat",
            font=(ui_f, 9, "bold"),
            padding=(12, 6)
        )
        style.map(
            "Success.TButton",
            background=[("active", c["accent_green_hover"]), ("pressed", c["accent_green_hover"])],
            foreground=[("active", "#ffffff")]
        )

        # Кнопка Опасности / Удаления (Сдержанный минималистичный акцент)
        danger_bg = "#291a1e" if self.theme_name == "dark" else "#fee2e2"
        danger_fg = "#f87171" if self.theme_name == "dark" else "#b91c1c"
        danger_hover = "#392027" if self.theme_name == "dark" else "#fecaca"
        style.configure(
            "Danger.TButton",
            background=danger_bg,
            foreground=danger_fg,
            borderwidth=1,
            bordercolor=c["border"],
            focuscolor="none",
            relief="flat",
            font=(ui_f, 9, "bold"),
            padding=(10, 5)
        )
        style.map(
            "Danger.TButton",
            background=[("active", danger_hover), ("pressed", danger_hover)],
            foreground=[("active", c["accent_red"])],
            bordercolor=[("active", c["accent_red"])]
        )

        # Компактная кнопка панели инструментов (Action Toolbar)
        style.configure(
            "Tool.TButton",
            background=c["surface_bg"],
            foreground=c["fg"],
            borderwidth=1,
            bordercolor=c["border"],
            lightcolor=c["surface_bg"],
            darkcolor=c["surface_bg"],
            focuscolor="none",
            relief="flat",
            font=(ui_f, 9),
            padding=(7, 4)
        )
        style.map(
            "Tool.TButton",
            background=[("active", c["surface_hover"]), ("pressed", c["surface_active"])],
            foreground=[("active", c["fg_bright"])],
            bordercolor=[("active", c["border_light"])]
        )

        # Кнопка-чип (Pill) для быстрых папок и пресетов
        style.configure(
            "Pill.TButton",
            background=c["surface_bg"],
            foreground=c["fg_dim"],
            borderwidth=1,
            bordercolor=c["border"],
            focuscolor="none",
            relief="flat",
            font=(ui_f, 8, "bold"),
            padding=(6, 3)
        )
        style.map(
            "Pill.TButton",
            background=[("active", c["surface_hover"]), ("pressed", c["surface_active"])],
            foreground=[("active", c["fg_bright"])],
            bordercolor=[("active", c["border_light"])]
        )

        # -----------------------------------------------------------------
        # Поля ввода (TEntry)
        # -----------------------------------------------------------------
        style.configure(
            "TEntry",
            fieldbackground=c["entry_bg"],
            foreground=c["entry_fg"],
            insertcolor=c["fg_bright"],
            bordercolor=c["entry_border"],
            lightcolor=c["entry_border"],
            darkcolor=c["entry_border"],
            relief="flat",
            padding=(8, 6),
            font=(ui_f, 10)
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", c["accent"])],
            lightcolor=[("focus", c["accent"])],
            darkcolor=[("focus", c["accent"])]
        )

        # -----------------------------------------------------------------
        # Чекбоксы и радиокнопки
        # -----------------------------------------------------------------
        style.configure(
            "TCheckbutton",
            background=c["card_bg"],
            foreground=c["fg"],
            focuscolor="none",
            font=(ui_f, 9)
        )
        style.map(
            "TCheckbutton",
            background=[("active", c["card_bg"])],
            foreground=[("active", c["fg_bright"])],
            indicatorcolor=[("selected", c["accent"]), ("!selected", c["surface_bg"])]
        )

        style.configure(
            "TRadiobutton",
            background=c["card_bg"],
            foreground=c["fg"],
            focuscolor="none",
            font=(ui_f, 9)
        )
        style.map(
            "TRadiobutton",
            background=[("active", c["card_bg"])],
            foreground=[("active", c["fg_bright"])],
            indicatorcolor=[("selected", c["accent"]), ("!selected", c["surface_bg"])]
        )

        # -----------------------------------------------------------------
        # Прогресс-бар
        # -----------------------------------------------------------------
        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=c["surface_bg"],
            background=c["accent"],
            bordercolor=c["surface_bg"],
            borderwidth=0,
            thickness=4
        )

        # -----------------------------------------------------------------
        # Скроллбары
        # -----------------------------------------------------------------
        style.configure(
            "Vertical.TScrollbar",
            background=c["surface_bg"],
            troughcolor=c["card_bg"],
            bordercolor=c["card_bg"],
            arrowcolor=c["fg_dim"],
            borderwidth=0,
            arrowsize=9
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", c["surface_hover"])],
            arrowcolor=[("active", c["fg_bright"])]
        )

        style.configure(
            "Horizontal.TScrollbar",
            background=c["surface_bg"],
            troughcolor=c["card_bg"],
            bordercolor=c["card_bg"],
            arrowcolor=c["fg_dim"],
            borderwidth=0,
            arrowsize=9
        )
        style.map(
            "Horizontal.TScrollbar",
            background=[("active", c["surface_hover"])],
            arrowcolor=[("active", c["fg_bright"])]
        )

        # Разделитель
        style.configure("TSeparator", background=c["border"])
