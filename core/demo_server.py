"""
Учебный демо-сервер (Песочница) для безопасного обучения новичков.
Позволяет тренироваться загружать, скачивать и редактировать файлы без риска что-то сломать.
"""

from __future__ import annotations
import os
import posixpath
import shutil
import stat
import time
from typing import Callable, List, Optional

from core.file_utils import FileItem, get_app_data_dir
from core.sftp_client import CancelToken


def get_demo_dir() -> str:
    return os.path.join(get_app_data_dir(), "demo_sandbox")


def setup_demo_environment(base_dir: Optional[str] = None):
    """
    Создаёт начальные обучающие папки и файлы для новичка.
    """
    if not base_dir:
        base_dir = get_demo_dir()
    os.makedirs(base_dir, exist_ok=True)

    # 1. Приветственное письмо
    readme_path = os.path.join(base_dir, "ПРОЧИТАЙ_МЕНЯ.txt")
    if not os.path.exists(readme_path):
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(
                "===========================================================\n"
                "🎉 ДОБРО ПОЖАЛОВАТЬ В УЧЕБНЫЙ ДЕМО-СЕРВЕР EASY SFTP!\n"
                "===========================================================\n\n"
                "Это безопасная песочница, имитирующая реальный Linux-сервер.\n"
                "Здесь вы можете спокойно учиться и экспериментировать!\n\n"
                "🔥 С ЧЕГО НАЧАТЬ:\n"
                "1. СКАЧИВАНИЕ: Выделите этот файл и нажмите кнопку '⬅️ Скачать на компьютер'.\n"
                "   Он появится в левой панели (на вашем ПК).\n\n"
                "2. РЕДАКТИРОВАНИЕ: Дважды кликните по файлу 'website/index.html'.\n"
                "   Откроется встроенный редактор. Измените заголовок сайта и нажмите '💾 Сохранить'.\n\n"
                "3. ЗАГРУЗКА: Выберите любой файл или картинку на вашем компьютере (слева)\n"
                "   и нажмите кнопку '➡️ Загрузить на сервер'.\n\n"
                "4. СОЗДАНИЕ ПАПКИ: Нажмите '📁+ Новая папка' в правой панели и создайте папку 'мои_файлы'.\n\n"
                "5. ПРАВА ДОСТУПА (chmod): Кликните правой кнопкой мыши по любому файлу\n"
                "   и выберите 'Права доступа (chmod)', чтобы увидеть, как устроены права 755 и 644.\n\n"
                "Приятного обучения! Когда освоитесь, введите данные своего реального сервера\n"
                "в строке подключения наверху.\n"
            )

    # 2. Папка с сайтом
    web_dir = os.path.join(base_dir, "website")
    os.makedirs(web_dir, exist_ok=True)

    index_path = os.path.join(web_dir, "index.html")
    if not os.path.exists(index_path):
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(
                "<!DOCTYPE html>\n"
                "<html lang=\"ru\">\n"
                "<head>\n"
                "    <meta charset=\"UTF-8\">\n"
                "    <title>Мой первый сайт на сервере</title>\n"
                "    <link rel=\"stylesheet\" href=\"style.css\">\n"
                "</head>\n"
                "<body>\n"
                "    <div class=\"container\">\n"
                "        <h1>🚀 Сайт успешно опубликован!</h1>\n"
                "        <p>Этот файл находится на удалённом сервере в папке <code>/website/index.html</code>.</p>\n"
                "        <p>Вы можете отредактировать этот текст прямо через EasySFTP!</p>\n"
                "    </div>\n"
                "</body>\n"
                "</html>\n"
            )

    css_path = os.path.join(web_dir, "style.css")
    if not os.path.exists(css_path):
        with open(css_path, "w", encoding="utf-8") as f:
            f.write(
                "body {\n"
                "    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;\n"
                "    background: #0f172a;\n"
                "    color: #f8fafc;\n"
                "    display: flex;\n"
                "    justify-content: center;\n"
                "    align-items: center;\n"
                "    min-height: 100vh;\n"
                "    margin: 0;\n"
                "}\n"
                ".container {\n"
                "    background: #1e293b;\n"
                "    padding: 30px;\n"
                "    border-radius: 12px;\n"
                "    box-shadow: 0 10px 25px rgba(0,0,0,0.5);\n"
                "    text-align: center;\n"
                "}\n"
                "h1 { color: #38bdf8; }\n"
            )

    # 3. Папка со скриптами и конфигами
    scripts_dir = os.path.join(base_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    bot_path = os.path.join(scripts_dir, "telegram_bot.py")
    if not os.path.exists(bot_path):
        with open(bot_path, "w", encoding="utf-8") as f:
            f.write(
                "# Пример скрипта Telegram-бота на сервере\n"
                "import os\n"
                "import time\n\n"
                "BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_SECRET_TOKEN_HERE')\n\n"
                "def main():\n"
                "    print('Бот запущен на сервере...')\n"
                "    while True:\n"
                "        time.sleep(10)\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            )

    config_path = os.path.join(scripts_dir, "config.json")
    if not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(
                "{\n"
                "  \"server_name\": \"Учебный сервер Linux\",\n"
                "  \"environment\": \"production\",\n"
                "  \"port\": 8080,\n"
                "  \"debug\": false,\n"
                "  \"database\": {\n"
                "    \"host\": \"127.0.0.1\",\n"
                "    \"port\": 5432,\n"
                "    \"user\": \"db_admin\"\n"
                "  }\n"
                "}\n"
            )


class DemoSFTPClient:
    """
    Симулятор SFTP-сервера для безопасной тренировки без интернета и сетевых портов.
    Реализует точно такой же интерфейс, как и реальный SFTPClient.
    Поддерживает мульти-директории, изоляцию (chroot) и режим песочницы (Sandbox).
    """
    def __init__(self, sandbox_root: Optional[str] = None):
        self.sandbox_root = os.path.abspath(sandbox_root if sandbox_root else get_demo_dir())
        self.current_path = "/"
        self.current_host = "Учебный сервер (Песочница)"
        self.current_port = 22
        self.current_user = "demo"
        self._is_connected = False
        self.allowed_directories: List[str] = ["/"]
        self.is_read_only = False
        self.is_sandbox = False
        self.demo_users: dict = {}
        setup_demo_environment(self.sandbox_root)

    def add_demo_user(self, user):
        """Регистрирует созданного пользователя с доступом к папкам и режимом песочницы."""
        dirs = user.allowed_directories if hasattr(user, "allowed_directories") else [user.jail_directory]
        mode = getattr(user, "mode", "sandbox")
        self.demo_users[user.username] = {
            "password": user.password,
            "allowed_directories": dirs,
            "mode": mode,
            "is_read_only": (mode == "read_only"),
            "is_sandbox": (mode == "sandbox")
        }

    def is_connected(self) -> bool:
        return self._is_connected

    def ensure_connected(self, force_reconnect: bool = False):
        if not self._is_connected:
            self._is_connected = True

    def connect(self, host: str = "demo-server", port: int = 22, username: str = "demo", password: str = "", **kwargs) -> str:
        setup_demo_environment(self.sandbox_root)
        self._is_connected = True
        self.current_user = username

        if username in self.demo_users:
            u_info = self.demo_users[username]
            self.allowed_directories = u_info["allowed_directories"]
            self.is_read_only = u_info["is_read_only"]
            self.is_sandbox = u_info["is_sandbox"]
            if len(self.allowed_directories) == 1 and self.allowed_directories[0] != "/":
                self.current_path = self.allowed_directories[0]
            else:
                self.current_path = "/"
        else:
            self.allowed_directories = ["/"]
            self.is_read_only = False
            self.is_sandbox = False
            self.current_path = "/"

        return self.current_path

    def disconnect(self):
        self._is_connected = False

    def pwd(self) -> str:
        return self.current_path

    def _is_path_allowed(self, path: str) -> bool:
        if "/" in self.allowed_directories:
            return True
        norm = posixpath.normpath(path)
        if norm == "/":
            return True
        for allowed in self.allowed_directories:
            allowed_norm = posixpath.normpath(allowed)
            if norm == allowed_norm or norm.startswith(allowed_norm + "/"):
                return True
        return False

    def _to_real_path(self, virtual_path: str) -> str:
        rel = virtual_path.replace("\\", "/").lstrip("/")
        norm = os.path.normpath(os.path.join(self.sandbox_root, rel))
        if not norm.startswith(self.sandbox_root):
            return self.sandbox_root
        return norm

    def cd(self, path: str) -> str:
        if not self._is_connected:
            raise RuntimeError("Нет подключения к учебному серверу.")

        if path == "..":
            if self.current_path == "/":
                new_path = "/"
            else:
                new_path = posixpath.dirname(self.current_path.rstrip("/"))
                if not new_path:
                    new_path = "/"
        elif path.startswith("/"):
            new_path = posixpath.normpath(path)
        elif path == "~":
            new_path = self.allowed_directories[0] if len(self.allowed_directories) == 1 else "/"
        else:
            new_path = posixpath.normpath(posixpath.join(self.current_path, path))

        if not self._is_path_allowed(new_path):
            raise PermissionError(f"Отказано в доступе: папка '{new_path}' не входит в список разрешённых директорий!")

        if new_path != "/":
            real = self._to_real_path(new_path)
            if not os.path.exists(real) or not os.path.isdir(real):
                raise FileNotFoundError(f"Папка '{new_path}' не найдена на сервере.")

        self.current_path = new_path
        return self.current_path

    def list_dir(self, remote_path: Optional[str] = None) -> List[FileItem]:
        if not self._is_connected:
            raise RuntimeError("Нет подключения к учебному серверу.")

        target = remote_path if remote_path else self.current_path

        # Если пользователь ограничен несколькими папками и находится в корне виртуальной системы
        if target == "/" and "/" not in self.allowed_directories:
            items: List[FileItem] = []
            for d in self.allowed_directories:
                folder_name = posixpath.basename(d.rstrip("/"))
                items.append(FileItem(
                    name=folder_name,
                    path=d,
                    size=0,
                    mtime=time.time(),
                    is_dir=True,
                    mode=0o755
                ))
            return items

        if not self._is_path_allowed(target):
            raise PermissionError(f"Доступ к папке '{target}' заблокирован администратором.")

        real = self._to_real_path(target)
        items: List[FileItem] = []
        if not os.path.exists(real):
            return items

        for entry in os.scandir(real):
            st = entry.stat()
            is_dir = entry.is_dir()
            vpath = posixpath.join(target, entry.name)
            items.append(FileItem(
                name=entry.name,
                path=vpath,
                size=st.st_size if not is_dir else 0,
                mtime=st.st_mtime,
                is_dir=is_dir,
                mode=st.st_mode
            ))

        items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
        return items

    def download_file(
        self,
        remote_path: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
        cancel_token: Optional[CancelToken] = None
    ):
        if not self._is_connected:
            raise RuntimeError("Нет подключения.")

        real = self._to_real_path(remote_path)
        total_size = os.path.getsize(real)
        filename = os.path.basename(real)

        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        chunk_size = 64 * 1024
        transferred = 0
        start = time.time()

        with open(real, "rb") as fin, open(local_path, "wb") as fout:
            while True:
                if cancel_token and cancel_token.is_cancelled:
                    raise InterruptedError("Скачивание отменено пользователем.")
                chunk = fin.read(chunk_size)
                if not chunk:
                    break
                fout.write(chunk)
                transferred += len(chunk)
                now = time.time()
                dt = now - start
                speed = transferred / dt if dt > 0 else 0
                if progress_callback:
                    progress_callback(transferred, total_size, speed, filename)
                time.sleep(0.01)  # Имитация сетевой задержки для наглядности прогресс-бара

        if progress_callback:
            progress_callback(total_size, total_size, 0, filename)

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
        cancel_token: Optional[CancelToken] = None
    ):
        if not self._is_connected:
            raise RuntimeError("Нет подключения.")
        if self.is_read_only:
            raise PermissionError("Отказано в доступе: у пользователя только права на чтение (Read-Only)!")
        if not self._is_path_allowed(remote_path):
            raise PermissionError("Отказано в доступе: путь не входит в список разрешённых папок пользователя!")

        real = self._to_real_path(remote_path)
        total_size = os.path.getsize(local_path)
        filename = os.path.basename(local_path)

        os.makedirs(os.path.dirname(real), exist_ok=True)

        chunk_size = 64 * 1024
        transferred = 0
        start = time.time()

        with open(local_path, "rb") as fin, open(real, "wb") as fout:
            while True:
                if cancel_token and cancel_token.is_cancelled:
                    raise InterruptedError("Загрузка отменена пользователем.")
                chunk = fin.read(chunk_size)
                if not chunk:
                    break
                fout.write(chunk)
                transferred += len(chunk)
                now = time.time()
                dt = now - start
                speed = transferred / dt if dt > 0 else 0
                if progress_callback:
                    progress_callback(transferred, total_size, speed, filename)
                time.sleep(0.01)

        if progress_callback:
            progress_callback(total_size, total_size, 0, filename)

    def download_directory_recursive(
        self,
        remote_dir: str,
        local_dir: str,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
        cancel_token: Optional[CancelToken] = None
    ):
        os.makedirs(local_dir, exist_ok=True)
        items = self.list_dir(remote_dir)
        for item in items:
            if cancel_token and cancel_token.is_cancelled:
                raise InterruptedError("Скачивание отменено.")
            loc = os.path.join(local_dir, item.name)
            rem = posixpath.join(remote_dir, item.name)
            if item.is_dir:
                self.download_directory_recursive(rem, loc, progress_callback, cancel_token)
            else:
                self.download_file(rem, loc, progress_callback, cancel_token)

    def upload_directory_recursive(
        self,
        local_dir: str,
        remote_dir: str,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
        cancel_token: Optional[CancelToken] = None
    ):
        self.create_directory(remote_dir)
        for entry in os.scandir(local_dir):
            if cancel_token and cancel_token.is_cancelled:
                raise InterruptedError("Загрузка отменена.")
            rem = posixpath.join(remote_dir, entry.name)
            if entry.is_dir():
                self.upload_directory_recursive(entry.path, rem, progress_callback, cancel_token)
            elif entry.is_file():
                self.upload_file(entry.path, rem, progress_callback, cancel_token)

    def create_directory(self, remote_path: str):
        if self.is_read_only:
            raise PermissionError("Отказано в доступе: у пользователя только права на чтение (Read-Only)!")
        if not self._is_path_allowed(remote_path):
            raise PermissionError("Отказано в доступе: путь не входит в список разрешённых папок!")
        real = self._to_real_path(remote_path)
        os.makedirs(real, exist_ok=True)

    def delete_file(self, remote_path: str):
        if self.is_read_only:
            raise PermissionError("Отказано в доступе: у пользователя только права на чтение (Read-Only)!")
        if not self._is_path_allowed(remote_path):
            raise PermissionError("Отказано в доступе: путь не входит в список разрешённых папок!")
        real = self._to_real_path(remote_path)
        if os.path.exists(real):
            os.remove(real)

    def delete_directory_recursive(self, remote_path: str, cancel_token: Optional[CancelToken] = None):
        if self.is_read_only:
            raise PermissionError("Отказано в доступе: у пользователя только права на чтение (Read-Only)!")
        if not self._is_path_allowed(remote_path):
            raise PermissionError("Отказано в доступе: путь не входит в список разрешённых папок!")
        real = self._to_real_path(remote_path)
        if os.path.exists(real):
            shutil.rmtree(real)

    def rename(self, old_path: str, new_path: str):
        old_clean = old_path.rstrip("/")
        new_clean = new_path.rstrip("/")
        if not old_clean or not new_clean:
            raise ValueError("Путь не может быть пустым.")
        if self.is_read_only:
            raise PermissionError("Отказано в доступе: у пользователя только права на чтение (Read-Only)!")
        if not self._is_path_allowed(old_clean) or not self._is_path_allowed(new_clean):
            raise PermissionError("Отказано в доступе: путь не входит в список разрешённых папок!")
        r_old = self._to_real_path(old_clean)
        r_new = self._to_real_path(new_clean)
        os.rename(r_old, r_new)
        if self.current_path == old_clean:
            self.current_path = new_clean
        elif self.current_path.startswith(old_clean + "/"):
            self.current_path = new_clean + self.current_path[len(old_clean):]

    def chmod(self, remote_path: str, mode: int):
        if self.is_read_only:
            raise PermissionError("Отказано в доступе: у пользователя только права на чтение (Read-Only)!")
        real = self._to_real_path(remote_path)
        try:
            os.chmod(real, mode)
        except Exception:
            pass

    def read_text_file(self, remote_path: str, max_size_bytes: int = 10 * 1024 * 1024) -> str:
        real = self._to_real_path(remote_path)
        with open(real, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def write_text_file(self, remote_path: str, text: str, encoding: str = "utf-8"):
        if self.is_read_only:
            raise PermissionError("Отказано в доступе: у пользователя только права на чтение (Read-Only)!")
        if not self._is_path_allowed(remote_path):
            raise PermissionError("Отказано в доступе: путь не входит в список разрешённых папок!")
        real = self._to_real_path(remote_path)
        with open(real, "w", encoding=encoding) as f:
            f.write(text)
