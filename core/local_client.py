"""
Управление локальной файловой системой компьютера.
Определение дисков Windows (C:, D:), стандартных пользовательских папок и безопасная работа с файлами.
"""

from __future__ import annotations
import os
import shutil
import string
import sys
from typing import Dict, List, Optional
from pathlib import Path

from core.file_utils import FileItem


class LocalClient:
    """
    Интерфейс для работы с локальной файловой системой.
    """
    def __init__(self, start_dir: Optional[str] = None):
        if start_dir and os.path.exists(start_dir):
            self.current_path = os.path.abspath(start_dir)
        else:
            self.current_path = os.path.expanduser("~")

    def pwd(self) -> str:
        """Текущая рабочая локальная папка."""
        return self.current_path

    def cd(self, path: str) -> str:
        """Переходит в указанную папку."""
        if path == "..":
            new_path = os.path.dirname(self.current_path)
            if not new_path:
                new_path = self.current_path
        elif os.path.isabs(path):
            new_path = os.path.abspath(path)
        else:
            new_path = os.path.abspath(os.path.join(self.current_path, path))

        if not os.path.exists(new_path):
            raise FileNotFoundError(f"Локальная папка '{new_path}' не существует.")
        if not os.path.isdir(new_path):
            raise NotADirectoryError(f"'{new_path}' не является папкой.")

        self.current_path = new_path
        return self.current_path

    def list_dir(self, local_path: Optional[str] = None) -> List[FileItem]:
        """
        Возвращает список элементов в локальной папке.
        Сначала папки, затем файлы по алфавиту.
        """
        target = os.path.abspath(local_path if local_path else self.current_path)
        items: List[FileItem] = []

        try:
            with os.scandir(target) as entries:
                for entry in entries:
                    try:
                        stat_info = entry.stat(follow_symlinks=False)
                        is_dir = entry.is_dir(follow_symlinks=False)
                        is_link = entry.is_symlink()
                        size = stat_info.st_size if not is_dir else 0
                        mtime = stat_info.st_mtime
                        mode = stat_info.st_mode

                        items.append(FileItem(
                            name=entry.name,
                            path=entry.path,
                            size=size,
                            mtime=mtime,
                            is_dir=is_dir,
                            is_link=is_link,
                            mode=mode
                        ))
                    except (PermissionError, FileNotFoundError):
                        # Пропускаем недоступные системные файлы
                        continue
        except PermissionError as e:
            raise PermissionError(f"Нет прав для доступа к локальной папке '{target}'.") from e
        except Exception as e:
            raise RuntimeError(f"Ошибка чтения локальной папки '{target}': {e}") from e

        # Сортировка: сначала папки, затем файлы
        items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        return items

    def get_drives(self) -> List[str]:
        """Возвращает список доступных дисков на Windows."""
        drives = []
        if sys.platform == "win32":
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append(drive)
        else:
            drives.append("/")
        return drives

    def get_shortcuts(self) -> Dict[str, str]:
        """Быстрые ссылки на популярные папки пользователя."""
        home = os.path.expanduser("~")
        shortcuts = {
            "🏠 Домашняя папка": home,
        }

        desktop = os.path.join(home, "Desktop")
        if not os.path.exists(desktop):
            desktop = os.path.join(home, "Рабочий стол")
        if os.path.exists(desktop):
            shortcuts["🖥️ Рабочий стол"] = desktop

        downloads = os.path.join(home, "Downloads")
        if not os.path.exists(downloads):
            downloads = os.path.join(home, "Загрузки")
        if os.path.exists(downloads):
            shortcuts["📥 Загрузки"] = downloads

        documents = os.path.join(home, "Documents")
        if not os.path.exists(documents):
            documents = os.path.join(home, "Документы")
        if os.path.exists(documents):
            shortcuts["📁 Документы"] = documents

        return shortcuts

    def create_directory(self, path: str):
        """Создаёт локальную папку."""
        os.makedirs(path, exist_ok=True)

    def delete_file(self, path: str):
        """Удаляет локальный файл."""
        os.remove(path)

    def delete_directory_recursive(self, path: str):
        """Рекурсивно удаляет локальную папку."""
        shutil.rmtree(path)

    def ensure_connected(self, force_reconnect: bool = False):
        pass

    def rename(self, old_path: str, new_path: str):
        """Переименовывает локальный файл или папку."""
        old_path = old_path.rstrip("/\\")
        new_path = new_path.rstrip("/\\")
        os.rename(old_path, new_path)

    def open_in_system(self, path: str):
        """Открывает файл или папку в системной программе Windows."""
        if sys.platform == "win32":
            os.startfile(path)
        else:
            import subprocess
            subprocess.Popen(["xdg-open", path])
