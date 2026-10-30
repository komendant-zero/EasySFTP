"""
Модуль безопасного подключения и работы с удалённым сервером по протоколу SFTP.
Включает автоматический Keepalive (бесконечное соединение), автовосстановление
при обрывах связи и подробные объяснения ошибок на понятном русском языке.
"""

from __future__ import annotations
import os
import posixpath
import socket
import stat
import threading
import time
from typing import Callable, List, Optional, Any, Dict
import paramiko

from core.file_utils import FileItem


def translate_sftp_error(exc: Exception, host: str = "", port: int = 22, path: str = "") -> str:
    """
    Переводит технические ошибки сети и SSH на человеческий язык с рекомендациями для новичка.
    """
    msg = str(exc).lower()

    if isinstance(exc, paramiko.AuthenticationException):
        return (
            "Ошибка авторизации!\n"
            "Сервер отклонил логин или пароль (либо не подошёл SSH-ключ).\n\n"
            "💡 Что проверить:\n"
            "1. Проверьте правильность написания логина (часто: root, sftp_user, ubuntu, admin).\n"
            "2. Убедитесь, что пароль скопирован без лишних пробелов в начале или конце.\n"
            "3. Если используется ключ, убедитесь, что указан правильный закрытый ключ (.pem / .key)."
        )

    if isinstance(exc, socket.gaierror) or "getaddrinfo failed" in msg or "name or service not known" in msg:
        return (
            f"Не удалось найти сервер '{host}'!\n"
            "Компьютер не смог определить IP-адрес для этого имени хоста.\n\n"
            "💡 Что проверить:\n"
            "1. Проверьте адрес: нет ли опечаток или лишних символов (например, пробелов или 'sftp://').\n"
            "2. Проверьте подключение к интернету на вашем компьютере.\n"
            "3. Попробуйте указать прямой IP-адрес сервера (например, 192.168.1.50)."
        )

    if isinstance(exc, (ConnectionRefusedError, socket.timeout)) or "timed out" in msg or "connection refused" in msg:
        return (
            f"Не удалось подключиться к {host}:{port}!\n"
            "Сервер не отвечает или подключение сброшено.\n\n"
            "💡 Что проверить:\n"
            f"1. Убедитесь, что порт указан верно (для AmneziaVPN часто 222, а не 22).\n"
            "2. Проверьте, включён ли сервер и запущен ли на нём SFTP/SSH.\n"
            "3. Возможно, порт заблокирован файрволом вашего провайдера или хостинга."
        )

    if isinstance(exc, PermissionError) or "permission denied" in msg or getattr(exc, "errno", None) == 13:
        target_info = f" к '{path}'" if path else ""
        return (
            f"Отказано в доступе (Permission Denied){target_info}!\n\n"
            "У пользователя недостаточно прав на сервере для этой папки.\n\n"
            "💡 Как это решить:\n"
            "1. В AmneziaVPN и Docker SFTP корень сервера '/' защищён от записи и чтения обычными пользователями.\n"
            "   Ваши рабочие папки находятся внутри (обычно '/sftp_user', '/upload' или '.').\n"
            "2. Укажите начальную папку (например, '/sftp_user') в строке пути или настройках подключения.\n"
            "3. Если вы настраиваете свой сервер и хотите дать права пользователю, выполните на сервере через SSH:\n"
            "   sudo chown -R sftp_user:sftp_user /путь/к/папке\n"
            "   sudo chmod -R 775 /путь/к/папке"
        )

    if isinstance(exc, FileNotFoundError) or "no such file" in msg:
        return (
            "Файл или папка не найдены на сервере!\n"
            "Возможно, путь был перемещён, переименован или удалён."
        )

    if "host key" in msg:
        return (
            "Предупреждение о ключе хоста (Host Key)!\n"
            "Ключ сервера изменился или сервер подключается впервые.\n"
            f"Детали: {exc}"
        )

    return f"Произошла ошибка при работе с сервером:\n{exc}"


class CancelToken:
    """
    Токен для безопасной отмены длительных операций передачи файлов.
    """
    def __init__(self):
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def reset(self):
        self._cancelled = False

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled


class SFTPClient:
    """
    Надёжный SFTP-клиент с поддержкой рекурсивной передачи,
    отслеживания прогресса, бесконечного поддержания соединения (Keepalive)
    и автоматического переподключения при разрывах связи.
    """
    def __init__(self):
        self.ssh: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
        self.current_host: str = ""
        self.current_port: int = 22
        self.current_user: str = ""
        self.current_path: str = "/"
        self._last_connect_args: Optional[Dict[str, Any]] = None
        self._manual_disconnect: bool = False
        self._lock = threading.RLock()
        self._watchdog_thread: Optional[threading.Thread] = None
        self._watchdog_stop = threading.Event()
        self._keepalive_interval: int = 10

    def is_connected(self) -> bool:
        """Проверяет, активно ли подключение к SFTP-серверу."""
        if not self.ssh or not self.sftp:
            return False
        try:
            transport = self.ssh.get_transport()
            return bool(transport and transport.is_active())
        except Exception:
            return False

    def _apply_keepalive(self, client: paramiko.SSHClient):
        """Включает SSH и TCP Keepalive для поддержания бесконечного соединения."""
        try:
            transport = client.get_transport()
            if transport:
                # Отправка SSH keepalive пакетов каждые 10 секунд
                transport.set_keepalive(self._keepalive_interval)
                sock = transport.sock
                if sock and hasattr(sock, "setsockopt"):
                    # Включаем проверку TCP Keepalive на уровне сокета ОС
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    if hasattr(socket, "TCP_KEEPIDLE"):
                        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
                    elif hasattr(socket, "TCP_KEEPALIVE"):
                        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, 30)
                    if hasattr(socket, "TCP_KEEPINTVL"):
                        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
                    if hasattr(socket, "TCP_KEEPCNT"):
                        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
        except Exception:
            pass

    def _start_keepalive_watchdog(self):
        """Запускает фоновый поток отслеживания и поддержания связи."""
        self._stop_keepalive_watchdog()
        self._watchdog_stop.clear()
        self._watchdog_thread = threading.Thread(
            target=self._keepalive_watchdog_loop,
            daemon=True,
            name="SFTP-KeepAlive-Watchdog"
        )
        self._watchdog_thread.start()

    def _stop_keepalive_watchdog(self):
        """Останавливает фоновый поток поддержания связи."""
        self._watchdog_stop.set()
        self._watchdog_thread = None

    def _keepalive_watchdog_loop(self):
        """Фоновый цикл проверки активности и упреждающего переподключения."""
        while not self._watchdog_stop.wait(timeout=self._keepalive_interval):
            if self._manual_disconnect:
                break
            with self._lock:
                if self._manual_disconnect:
                    break
                try:
                    if not self.is_connected():
                        self._reconnect()
                    else:
                        transport = self.ssh.get_transport() if self.ssh else None
                        if transport and transport.is_active():
                            transport.send_ignore()
                        else:
                            self._reconnect()
                except Exception:
                    try:
                        self._reconnect()
                    except Exception:
                        pass

    def _close_handles(self):
        """Безопасно закрывает текущие дескрипторы без сброса настроек переподключения."""
        if self.sftp:
            try:
                self.sftp.close()
            except Exception:
                pass
            self.sftp = None

        if self.ssh:
            try:
                self.ssh.close()
            except Exception:
                pass
            self.ssh = None

    def _reconnect(self) -> bool:
        """
        Восстанавливает разорванное соединение с сохранением текущей рабочей папки.
        """
        if self._manual_disconnect or not self._last_connect_args:
            return False

        saved_path = self.current_path
        args = dict(self._last_connect_args)

        self._close_handles()

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        pkey = None
        key_filename = args.get("key_filename")
        if key_filename and os.path.exists(key_filename):
            try:
                pkey = self._load_private_key(key_filename, args.get("passphrase"))
            except Exception:
                pkey = None

        timeout = args.get("timeout", 15)
        try:
            client.connect(
                hostname=self.current_host,
                port=self.current_port,
                username=self.current_user,
                password=args.get("password") or None,
                pkey=pkey,
                key_filename=None if pkey else key_filename,
                timeout=timeout,
                banner_timeout=timeout,
                auth_timeout=timeout,
                look_for_keys=False,
                allow_agent=False
            )
            self.ssh = client
            self._apply_keepalive(client)
            self.sftp = client.open_sftp()

            # Восстанавливаем папку, если возможно
            if saved_path:
                try:
                    self.sftp.stat(saved_path)
                    self.current_path = saved_path
                except Exception:
                    pass
            return True
        except Exception:
            self._close_handles()
            return False

    def ensure_connected(self, force_reconnect: bool = False):
        """
        Гарантирует активное подключение к серверу.
        При необходимости автоматически восстанавливает связь.
        """
        with self._lock:
            if not force_reconnect and self.is_connected():
                return
            if self._manual_disconnect:
                raise RuntimeError("Нет активного подключения к серверу (сессия закрыта).")
            if not self._last_connect_args:
                raise RuntimeError("Нет сохранённых параметров подключения.")

            success = self._reconnect()
            if not success or not self.is_connected():
                raise RuntimeError("Связь с сервером была потеряна, попытка автоматического переподключения не удалась.")

    def _execute_with_retry(self, operation: Callable[[], Any]) -> Any:
        """
        Выполняет файловую операцию. При сетевом сбое (EOF/SSH timeout)
        прозрачно переподключается и повторяет операцию один раз.
        """
        self.ensure_connected()
        try:
            return operation()
        except (paramiko.SSHException, EOFError, socket.error, BrokenPipeError, ConnectionResetError):
            self.ensure_connected(force_reconnect=True)
            return operation()

    def connect(
        self,
        host: str,
        port: int = 22,
        username: str = "root",
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
        passphrase: Optional[str] = None,
        initial_dir: Optional[str] = None,
        timeout: int = 15
    ) -> str:
        """
        Устанавливает защищённое бесконечное SFTP соединение.
        Автоматически определяет доступную рабочую папку (для AmneziaVPN / chroot)
        и запускает фоновый Keepalive-монитор.
        """
        self.disconnect(manual=False)

        host = host.strip()
        if host.startswith("sftp://"):
            host = host[7:]
        if host.startswith("ssh://"):
            host = host[6:]
        if "/" in host:
            host = host.split("/")[0]

        self.current_host = host
        self.current_port = port
        self.current_user = username.strip()
        self._manual_disconnect = False
        self._last_connect_args = {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "key_filename": key_filename,
            "passphrase": passphrase,
            "initial_dir": initial_dir,
            "timeout": timeout,
        }

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        pkey = None
        if key_filename and os.path.exists(key_filename):
            pkey = self._load_private_key(key_filename, passphrase)

        try:
            client.connect(
                hostname=self.current_host,
                port=self.current_port,
                username=self.current_user,
                password=password if password else None,
                pkey=pkey,
                key_filename=None if pkey else key_filename,
                timeout=timeout,
                banner_timeout=timeout,
                auth_timeout=timeout,
                look_for_keys=False,
                allow_agent=False
            )
            self.ssh = client
            self._apply_keepalive(client)
            self.sftp = client.open_sftp()

            # Если пользователь указал папку вручную
            if initial_dir and initial_dir.strip():
                self.current_path = initial_dir.strip()
            else:
                # Умное определение рабочей папки (особенно важно для AmneziaVPN / Docker SFTP)
                self.current_path = self._discover_accessible_directory()

            self._start_keepalive_watchdog()
            return self.current_path
        except Exception as e:
            self.disconnect(manual=True)
            friendly_msg = translate_sftp_error(e, self.current_host, self.current_port)
            raise RuntimeError(friendly_msg) from e

    def _discover_accessible_directory(self) -> str:
        """
        Автоматически находит доступную для пользователя рабочую директорию.
        В AmneziaVPN и Chroot корень '/' защищён от обычных пользователей,
        поэтому проверяются персональные папки (например, /sftp_user, ., /upload).
        """
        candidates = []
        try:
            norm = self.sftp.normalize(".")
            if norm and norm != "/":
                candidates.append(norm)
        except Exception:
            pass

        candidates.extend([
            f"/{self.current_user}",
            ".",
            "/upload",
            "/uploads",
            "/data",
            "/files",
            "/share",
            f"/home/{self.current_user}",
            "/"
        ])

        seen = set()
        for cand in candidates:
            if cand in seen:
                continue
            seen.add(cand)
            try:
                self.sftp.listdir_attr(cand)
                return cand
            except Exception:
                continue

        return "/"

    def _load_private_key(self, path: str, passphrase: Optional[str] = None):
        """Пытается загрузить приватный ключ различных форматов."""
        errors = []
        key_classes = [
            paramiko.RSAKey,
            paramiko.Ed25519Key,
            paramiko.ECDSAKey,
            paramiko.DSSKey
        ]
        for key_cls in key_classes:
            try:
                return key_cls.from_private_key_file(path, password=passphrase)
            except Exception as e:
                errors.append(str(e))
        raise ValueError(
            f"Не удалось распознать формат закрытого SSH-ключа '{os.path.basename(path)}'.\n"
            f"Убедитесь, что файл является валидным ключом OpenSSH (RSA, Ed25519) и введён верный пароль от ключа, если он зашифрован."
        )

    def disconnect(self, manual: bool = True):
        """Закрывает SFTP и SSH сессии."""
        if manual:
            self._manual_disconnect = True
            self._stop_keepalive_watchdog()
        with self._lock:
            self._close_handles()

    def pwd(self) -> str:
        """Возвращает текущую рабочую директорию на сервере."""
        return self.current_path

    def cd(self, path: str) -> str:
        """
        Переходит в указанную директорию на сервере и возвращает нормализованный путь.
        """
        def _op():
            if path == "..":
                new_path = posixpath.dirname(self.current_path.rstrip("/"))
                if not new_path:
                    new_path = "/"
            elif path.startswith("/"):
                new_path = posixpath.normpath(path)
            elif path == "~":
                new_path = self.sftp.normalize(".")
            else:
                new_path = posixpath.normpath(posixpath.join(self.current_path, path))

            # Проверяем доступность папки
            try:
                stat_info = self.sftp.stat(new_path)
                if not stat.S_ISDIR(stat_info.st_mode):
                    raise NotADirectoryError(f"'{new_path}' не является папкой.")
            except Exception:
                try:
                    self.sftp.listdir_attr(new_path)
                except Exception as e:
                    friendly = translate_sftp_error(e, self.current_host, self.current_port, new_path)
                    raise RuntimeError(friendly) from e

            self.current_path = new_path
            return self.current_path

        return self._execute_with_retry(_op)

    def list_dir(self, remote_path: Optional[str] = None) -> List[FileItem]:
        """
        Получает список файлов и папок в директории на сервере.
        Папки сортируются первыми, затем файлы по алфавиту.
        В случае Permission Denied на корне автоматически находит доступную папку пользователя.
        """
        def _op():
            target = remote_path if remote_path else self.current_path
            items: List[FileItem] = []
            attrs = None

            try:
                attrs = self.sftp.listdir_attr(target)
            except IOError as e:
                # Если корень '/' заблокирован, автоматически переключаемся на рабочую папку (/sftp_user, ., /upload)
                if target in ("/", "") and ("permission" in str(e).lower() or getattr(e, "errno", None) == 13):
                    cand = self._discover_accessible_directory()
                    if cand and cand != target:
                        self.current_path = cand
                        target = cand
                        try:
                            attrs = self.sftp.listdir_attr(cand)
                        except Exception:
                            pass
                if attrs is None:
                    friendly = translate_sftp_error(e, self.current_host, self.current_port, target)
                    raise RuntimeError(friendly) from e

            for attr in attrs:
                name = attr.filename
                if name in (".", ".."):
                    continue

                full_path = posixpath.join(target, name)
                mode = attr.st_mode if attr.st_mode is not None else 0
                is_dir = stat.S_ISDIR(mode)
                is_link = stat.S_ISLNK(mode)
                size = attr.st_size if attr.st_size is not None else 0
                mtime = attr.st_mtime if attr.st_mtime is not None else 0.0

                # Если это символическая ссылка, пробуем узнать, куда она ведёт
                link_target = ""
                if is_link:
                    try:
                        link_target = self.sftp.readlink(full_path)
                        target_stat = self.sftp.stat(full_path)
                        is_dir = stat.S_ISDIR(target_stat.st_mode)
                    except Exception:
                        pass

                items.append(FileItem(
                    name=name,
                    path=full_path,
                    size=size,
                    mtime=mtime,
                    is_dir=is_dir,
                    is_link=is_link,
                    mode=mode,
                    link_target=link_target
                ))

            # Сортировка: сначала папки, затем файлы, без учёта регистра
            items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
            return items

        return self._execute_with_retry(_op)

    def download_file(
        self,
        remote_path: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
        cancel_token: Optional[CancelToken] = None
    ):
        """
        Скачивает один файл с сервера на локальный компьютер.
        progress_callback(transferred_bytes, total_bytes, speed_bytes_per_sec, current_filename)
        """
        self.ensure_connected()

        remote_stat = self.sftp.stat(remote_path)
        total_size = remote_stat.st_size
        filename = posixpath.basename(remote_path)

        # Создаём родительскую локальную папку, если нужно
        local_dir = os.path.dirname(local_path)
        if local_dir:
            os.makedirs(local_dir, exist_ok=True)

        start_time = time.time()
        last_transferred = 0
        last_time = start_time

        def cb(transferred: int, total: int):
            nonlocal last_transferred, last_time
            if cancel_token and cancel_token.is_cancelled:
                raise InterruptedError("Операция скачивания отменена пользователем.")

            now = time.time()
            dt = now - last_time
            if dt >= 0.15 or transferred == total:
                speed = (transferred - last_transferred) / dt if dt > 0 else 0.0
                last_transferred = transferred
                last_time = now
                if progress_callback:
                    progress_callback(transferred, total_size, speed, filename)

        try:
            self.sftp.get(remote_path, local_path, callback=cb)
            if progress_callback:
                progress_callback(total_size, total_size, 0.0, filename)
        except Exception as e:
            if os.path.exists(local_path) and cancel_token and cancel_token.is_cancelled:
                try:
                    os.remove(local_path)
                except Exception:
                    pass
            raise e

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
        cancel_token: Optional[CancelToken] = None
    ):
        """
        Загружает один локальный файл на удалённый сервер.
        """
        self.ensure_connected()

        total_size = os.path.getsize(local_path)
        filename = os.path.basename(local_path)

        start_time = time.time()
        last_transferred = 0
        last_time = start_time

        def cb(transferred: int, total: int):
            nonlocal last_transferred, last_time
            if cancel_token and cancel_token.is_cancelled:
                raise InterruptedError("Операция загрузки отменена пользователем.")

            now = time.time()
            dt = now - last_time
            if dt >= 0.15 or transferred == total:
                speed = (transferred - last_transferred) / dt if dt > 0 else 0.0
                last_transferred = transferred
                last_time = now
                if progress_callback:
                    progress_callback(transferred, total_size, speed, filename)

        try:
            self.sftp.put(local_path, remote_path, callback=cb)
            if progress_callback:
                progress_callback(total_size, total_size, 0.0, filename)
        except Exception as e:
            if cancel_token and cancel_token.is_cancelled:
                try:
                    self.sftp.remove(remote_path)
                except Exception:
                    pass
            raise e

    def download_directory_recursive(
        self,
        remote_dir: str,
        local_dir: str,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
        cancel_token: Optional[CancelToken] = None
    ):
        """
        Рекурсивно скачивает папку со всеми вложенными файлами и подпапками.
        """
        self.ensure_connected()

        os.makedirs(local_dir, exist_ok=True)
        items = self.list_dir(remote_dir)

        for item in items:
            if cancel_token and cancel_token.is_cancelled:
                raise InterruptedError("Скачивание отменено пользователем.")

            local_item_path = os.path.join(local_dir, item.name)
            remote_item_path = posixpath.join(remote_dir, item.name)

            if item.is_dir:
                self.download_directory_recursive(
                    remote_item_path, local_item_path, progress_callback, cancel_token
                )
            else:
                self.download_file(
                    remote_item_path, local_item_path, progress_callback, cancel_token
                )

    def upload_directory_recursive(
        self,
        local_dir: str,
        remote_dir: str,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None,
        cancel_token: Optional[CancelToken] = None
    ):
        """
        Рекурсивно загружает локальную папку со всеми вложенными файлами и подпапками на сервер.
        """
        self.ensure_connected()

        self.create_directory(remote_dir)

        for entry in os.scandir(local_dir):
            if cancel_token and cancel_token.is_cancelled:
                raise InterruptedError("Загрузка отменена пользователем.")

            remote_item_path = posixpath.join(remote_dir, entry.name)
            if entry.is_dir():
                self.upload_directory_recursive(
                    entry.path, remote_item_path, progress_callback, cancel_token
                )
            elif entry.is_file():
                self.upload_file(
                    entry.path, remote_item_path, progress_callback, cancel_token
                )

    def create_directory(self, remote_path: str):
        """Создаёт директорию на сервере (включая родительские при необходимости)."""
        def _op():
            parts = [p for p in remote_path.split("/") if p]
            accum = "/"
            for part in parts:
                accum = posixpath.join(accum, part)
                try:
                    self.sftp.stat(accum)
                except IOError:
                    try:
                        self.sftp.mkdir(accum)
                    except IOError as e:
                        friendly = translate_sftp_error(e, self.current_host, self.current_port)
                        raise RuntimeError(friendly) from e

        self._execute_with_retry(_op)

    def delete_file(self, remote_path: str):
        """Удаляет файл на сервере."""
        def _op():
            try:
                self.sftp.remove(remote_path)
            except IOError as e:
                friendly = translate_sftp_error(e, self.current_host, self.current_port)
                raise RuntimeError(friendly) from e

        self._execute_with_retry(_op)

    def delete_directory_recursive(self, remote_path: str, cancel_token: Optional[CancelToken] = None):
        """Рекурсивно удаляет папку и всё её содержимое на сервере."""
        self.ensure_connected()
        items = self.list_dir(remote_path)
        for item in items:
            if cancel_token and cancel_token.is_cancelled:
                raise InterruptedError("Удаление отменено пользователем.")
            if item.is_dir:
                self.delete_directory_recursive(item.path, cancel_token)
            else:
                self.delete_file(item.path)

        def _op():
            try:
                self.sftp.rmdir(remote_path)
            except IOError as e:
                friendly = translate_sftp_error(e, self.current_host, self.current_port)
                raise RuntimeError(friendly) from e

        self._execute_with_retry(_op)

    def rename(self, old_path: str, new_path: str):
        """
        Переименовывает или перемещает файл/папку на сервере.
        Корректно обрабатывает директории с завершающими слэшами.
        """
        old_clean = old_path.rstrip("/")
        new_clean = new_path.rstrip("/")
        if not old_clean or not new_clean:
            raise ValueError("Путь не может быть пустым.")

        def _op():
            try:
                self.sftp.rename(old_clean, new_clean)
            except IOError as e:
                friendly = translate_sftp_error(e, self.current_host, self.current_port, old_clean)
                raise RuntimeError(friendly) from e

        self._execute_with_retry(_op)

        # Актуализируем текущий путь, если переименована текущая или родительская папка
        if self.current_path == old_clean:
            self.current_path = new_clean
        elif self.current_path.startswith(old_clean + "/"):
            self.current_path = new_clean + self.current_path[len(old_clean):]

    def chmod(self, remote_path: str, mode: int):
        """Изменяет права доступа файла или папки на сервере."""
        def _op():
            try:
                self.sftp.chmod(remote_path, mode)
            except IOError as e:
                friendly = translate_sftp_error(e, self.current_host, self.current_port)
                raise RuntimeError(friendly) from e

        self._execute_with_retry(_op)

    def read_text_file(self, remote_path: str, max_size_bytes: int = 10 * 1024 * 1024) -> str:
        """
        Считывает текстовый файл с сервера (до 10 МБ).
        Автоматически определяет кодировку (UTF-8, CP1251, latin1).
        """
        def _op():
            stat_info = self.sftp.stat(remote_path)
            if stat_info.st_size > max_size_bytes:
                raise ValueError(
                    f"Файл слишком большой ({stat_info.st_size / (1024*1024):.1f} МБ) "
                    f"для встроенного редактора (лимит: {max_size_bytes // (1024*1024)} МБ)."
                )

            with self.sftp.open(remote_path, "rb") as f:
                raw_data = f.read()

            for encoding in ["utf-8", "utf-8-sig", "cp1251", "latin-1"]:
                try:
                    return raw_data.decode(encoding)
                except UnicodeDecodeError:
                    continue

            return raw_data.decode("utf-8", errors="replace")

        return self._execute_with_retry(_op)

    def write_text_file(self, remote_path: str, text: str, encoding: str = "utf-8"):
        """
        Записывает текстовый контент в файл на сервере.
        """
        def _op():
            raw_data = text.encode(encoding)
            with self.sftp.open(remote_path, "wb") as f:
                f.write(raw_data)

        self._execute_with_retry(_op)
