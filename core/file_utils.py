"""
Вспомогательные утилиты для работы с файлами и форматирования.
Понятные единицы измерения, иконки типов файлов и форматирование дат на русском языке.
"""

from __future__ import annotations
import os
import stat
import datetime
from dataclasses import dataclass
from typing import Tuple


TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".log", ".json", ".yaml", ".yml",
    ".xml", ".csv", ".tsv", ".ini", ".conf", ".cfg", ".env",
    ".py", ".pyw", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm",
    ".css", ".scss", ".sass", ".less", ".php", ".sh", ".bash",
    ".bat", ".cmd", ".ps1", ".sql", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".java", ".go", ".rs", ".rb", ".lua", ".dockerfile",
    ".gitignore", ".gitattributes", ".editorconfig", ".toml", ".rst"
}

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".tiff"
}

ARCHIVE_EXTENSIONS = {
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".xz", ".txz",
    ".rar", ".7z", ".iso"
}

MEDIA_EXTENSIONS = {
    ".mp3", ".wav", ".ogg", ".flac", ".m4a", ".mp4", ".mkv", ".avi",
    ".mov", ".wmv", ".webm"
}

EXECUTABLE_EXTENSIONS = {
    ".exe", ".msi", ".dll", ".bin", ".app", ".deb", ".rpm"
}


def format_size(size_bytes: int) -> str:
    """
    Форматирует размер файла в понятный человеку русский формат (Б, КБ, МБ, ГБ).
    """
    if size_bytes is None or size_bytes < 0:
        return "—"
    if size_bytes == 0:
        return "0 Б"

    units = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
    size = float(size_bytes)
    unit_idx = 0
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1

    if unit_idx == 0:
        return f"{int(size)} {units[unit_idx]}"
    elif size >= 100:
        return f"{size:.0f} {units[unit_idx]}"
    elif size >= 10:
        return f"{size:.1f} {units[unit_idx]}"
    else:
        return f"{size:.2f} {units[unit_idx]}"


def format_time(timestamp: float | None) -> str:
    """
    Форматирует timestamp в строку вида 'ДД.ММ.ГГГГ ЧЧ:ММ'.
    """
    if not timestamp or timestamp <= 0:
        return "—"
    try:
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return "—"


def get_file_icon_and_type(filename: str, is_dir: bool) -> Tuple[str, str]:
    """
    Возвращает понятную иконку и текстовое описание типа файла.
    """
    if is_dir:
        return "📁", "Папка с файлами"

    lower_name = filename.lower()
    _, ext = os.path.splitext(lower_name)

    if ext in TEXT_EXTENSIONS or lower_name in {".env", "dockerfile", "makefile", "license", "readme"}:
        if ext in {".py", ".js", ".ts", ".html", ".css", ".php", ".c", ".cpp", ".cs", ".go", ".rs"}:
            return "💻", f"Исходный код ({ext.lstrip('.').upper()})"
        if ext in {".json", ".yaml", ".yml", ".ini", ".conf", ".cfg", ".env", ".toml"}:
            return "⚙️", "Файл конфигурации"
        return "📝", "Текстовый документ"

    if ext in IMAGE_EXTENSIONS:
        return "🖼️", f"Изображение ({ext.lstrip('.').upper()})"

    if ext in ARCHIVE_EXTENSIONS:
        return "📦", f"Архив ({ext.lstrip('.').upper()})"

    if ext in MEDIA_EXTENSIONS:
        return "🎬", "Медиафайл (Аудио/Видео)"

    if ext in EXECUTABLE_EXTENSIONS:
        return "🚀", "Исполняемая программа"

    if ext in {".pdf"}:
        return "📑", "Документ PDF"

    return "📄", f"Файл {ext.upper() if ext else ''}".strip()


def is_text_file(filename: str) -> bool:
    """
    Проверяет, является ли файл текстовым (по расширению или имени).
    """
    lower = filename.lower()
    _, ext = os.path.splitext(lower)
    return ext in TEXT_EXTENSIONS or lower in {".env", "dockerfile", "makefile", "license", "readme", ".gitignore"}


def parse_mode_to_octal(mode: int | None) -> str:
    """
    Преобразует права доступа в стандартный 3-значный код (например, 755, 644).
    """
    if mode is None:
        return "—"
    try:
        return oct(mode & 0o777)[2:].zfill(3)
    except Exception:
        return "—"


def parse_mode_to_rwx(mode: int | None) -> str:
    """
    Преобразует права доступа в строку вида '-rwxr-xr-x' или 'drwxr-xr-x'.
    """
    if mode is None:
        return "—"
    try:
        return stat.filemode(mode)
    except Exception:
        return "—"


def get_app_data_dir() -> str:
    """
    Возвращает безопасную директорию для хранения данных программы (.easysftp).
    Поддерживает портативный режим в папке проекта с откатом на временную папку.
    """
    # 1. Сначала пробуем директорию в корне приложения (портативный режим)
    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_data = os.path.join(app_root, ".easysftp")
    try:
        os.makedirs(local_data, exist_ok=True)
        test_file = os.path.join(local_data, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return local_data
    except Exception:
        pass

    # 2. Пробуем домашнюю папку пользователя
    user_data = os.path.join(os.path.expanduser("~"), ".easysftp")
    try:
        os.makedirs(user_data, exist_ok=True)
        test_file = os.path.join(user_data, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return user_data
    except Exception:
        pass

    # 3. Откат на временную директорию системы
    import tempfile
    temp_data = os.path.join(tempfile.gettempdir(), "easysftp_data")
    os.makedirs(temp_data, exist_ok=True)
    return temp_data


@dataclass
class FileItem:
    """
    Универсальное представление файла или папки для локального и удалённого списков.
    """
    name: str
    path: str
    size: int
    mtime: float
    is_dir: bool
    is_link: bool = False
    mode: int = 0
    link_target: str = ""

    @property
    def formatted_size(self) -> str:
        if self.is_dir:
            return "Папка"
        return format_size(self.size)

    @property
    def formatted_time(self) -> str:
        return format_time(self.mtime)

    @property
    def icon_and_type(self) -> Tuple[str, str]:
        return get_file_icon_and_type(self.name, self.is_dir)

    @property
    def icon(self) -> str:
        return self.icon_and_type[0]

    @property
    def type_desc(self) -> str:
        return self.icon_and_type[1]

    @property
    def permissions_octal(self) -> str:
        return parse_mode_to_octal(self.mode)

    @property
    def permissions_rwx(self) -> str:
        return parse_mode_to_rwx(self.mode)
