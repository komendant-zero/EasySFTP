"""
Менеджер настроек и сохранённых серверов (закладок).
Хранит историю подключений и закладки в формате JSON.
"""

from __future__ import annotations
import base64
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional
from core.file_utils import get_app_data_dir


def get_default_config_path() -> str:
    return os.path.join(get_app_data_dir(), "config.json")


def _encode_str(val: str) -> str:
    """Базовое скрытие паролей от случайного взгляда в текстовом файле."""
    if not val:
        return ""
    try:
        return base64.b64encode(val.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def _decode_str(val: str) -> str:
    """Декодирование скрытой строки."""
    if not val:
        return ""
    try:
        return base64.b64decode(val.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


class ConfigManager:
    """
    Управляет сохранёнными серверами, историей и настройками EasySFTP.
    """
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path if config_path else get_default_config_path()
        self.config_dir = os.path.dirname(self.config_path)
        self.data: Dict[str, Any] = {
            "servers": [],
            "recent_servers": [],
            "last_connection": {
                "host": "",
                "port": 22,
                "username": "root",
                "auth_type": "password",
                "key_path": "",
                "password": ""
            },
            "settings": {
                "theme": "dark",
                "confirm_delete": True,
                "show_hidden_files": False,
                "last_local_dir": ""
            }
        }
        self.load()

    def get_recent_servers(self) -> List[Dict[str, Any]]:
        """Возвращает список недавних серверов для входа в 1 клик."""
        recents = self.data.get("recent_servers", [])
        result = []
        for r in recents:
            r_copy = dict(r)
            if "encoded_pass" in r_copy:
                r_copy["password"] = _decode_str(r_copy["encoded_pass"])
            result.append(r_copy)
        # Сортировка по времени последнего входа (новые сверху)
        result.sort(key=lambda x: x.get("last_connected", 0), reverse=True)
        return result

    def add_recent_server(
        self,
        host: str,
        port: int,
        username: str,
        password: str = "",
        auth_type: str = "password",
        key_path: str = "",
        name: str = ""
    ):
        """Добавляет или обновляет сервер в списке недавних для быстрого входа."""
        if not host.strip():
            return

        recents = self.data.setdefault("recent_servers", [])
        clean_host = host.strip()
        clean_port = int(port)
        clean_user = username.strip()

        # Ищем существующую запись
        idx = next(
            (i for i, r in enumerate(recents)
             if r.get("host") == clean_host and r.get("port") == clean_port and r.get("username") == clean_user),
            None
        )

        record = {
            "host": clean_host,
            "port": clean_port,
            "username": clean_user,
            "auth_type": auth_type,
            "key_path": key_path.strip(),
            "encoded_pass": _encode_str(password) if password else (recents[idx].get("encoded_pass", "") if idx is not None else ""),
            "name": name.strip() or f"{clean_host}:{clean_port}",
            "last_connected": time.time()
        }

        if idx is not None:
            # Обновляем пароль, если передан новый
            if password:
                record["encoded_pass"] = _encode_str(password)
            recents.pop(idx)

        recents.insert(0, record)
        # Ограничиваем историю 10 серверами
        self.data["recent_servers"] = recents[:10]
        self.save()

    def remove_recent_server(self, host: str, port: int, username: str):
        """Удаляет сервер из списка недавних."""
        recents = self.data.get("recent_servers", [])
        self.data["recent_servers"] = [
            r for r in recents
            if not (r.get("host") == host and r.get("port") == int(port) and r.get("username") == username)
        ]
        self.save()

    def load(self):
        """Загружает настройки из файла JSON."""
        if not os.path.exists(self.config_path):
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    self.data.update(loaded)
        except Exception:
            # При повреждённом файле используем значения по умолчанию
            pass

    def save(self):
        """Сохраняет текущие настройки на диск."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # --- Управление закладками серверов ---

    def get_servers(self) -> List[Dict[str, Any]]:
        """Возвращает список всех сохранённых серверов."""
        servers = self.data.get("servers", [])
        result = []
        for s in servers:
            s_copy = dict(s)
            if "encoded_pass" in s_copy:
                s_copy["password"] = _decode_str(s_copy["encoded_pass"])
            result.append(s_copy)
        return result

    def get_server_by_id(self, server_id: str) -> Optional[Dict[str, Any]]:
        """Ищет сервер по ID."""
        for s in self.get_servers():
            if s.get("id") == server_id:
                return s
        return None

    def add_or_update_server(
        self,
        name: str,
        host: str,
        port: int = 22,
        username: str = "root",
        auth_type: str = "password",
        password: str = "",
        key_path: str = "",
        initial_remote_path: str = "/",
        server_id: Optional[str] = None
    ) -> str:
        """
        Добавляет новый сервер или обновляет существующий.
        Возвращает ID сервера.
        """
        sid = server_id if server_id else str(uuid.uuid4())
        record = {
            "id": sid,
            "name": name.strip() or host.strip(),
            "host": host.strip(),
            "port": int(port),
            "username": username.strip(),
            "auth_type": auth_type,
            "encoded_pass": _encode_str(password) if password else "",
            "key_path": key_path.strip(),
            "initial_remote_path": initial_remote_path.strip() or "/"
        }

        servers = self.data.setdefault("servers", [])
        idx = next((i for i, s in enumerate(servers) if s.get("id") == sid), None)
        if idx is not None:
            servers[idx] = record
        else:
            servers.append(record)

        self.save()
        return sid

    def delete_server(self, server_id: str):
        """Удаляет сохранённый сервер."""
        servers = self.data.get("servers", [])
        self.data["servers"] = [s for s in servers if s.get("id") != server_id]
        self.save()

    # --- Последнее подключение ---

    def set_last_connection(
        self,
        host: str,
        port: int,
        username: str,
        auth_type: str = "password",
        key_path: str = "",
        password: str = ""
    ):
        """Сохраняет параметры последнего успешного подключения."""
        self.data["last_connection"] = {
            "host": host.strip(),
            "port": int(port),
            "username": username.strip(),
            "auth_type": auth_type,
            "key_path": key_path.strip(),
            "encoded_pass": _encode_str(password) if password else ""
        }
        self.save()

    def get_last_connection(self) -> Dict[str, Any]:
        """Возвращает данные последнего подключения."""
        last = self.data.get("last_connection", {})
        res = dict(last)
        if "encoded_pass" in res:
            res["password"] = _decode_str(res["encoded_pass"])
        else:
            res["password"] = ""
        return res

    # --- Общие настройки программы ---

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.data.setdefault("settings", {}).get(key, default)

    def set_setting(self, key: str, value: Any):
        self.data.setdefault("settings", {})[key] = value
        self.save()
