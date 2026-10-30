"""
Умный распознаватель настроек SFTP из буфера обмена.
Автоматически считывает данные из AmneziaVPN, хостинг-панелей, ссылок sftp:// и заметок.
"""

from __future__ import annotations
import re
from typing import Dict, Optional


def parse_sftp_clipboard(text: str) -> Dict[str, str]:
    """
    Разбирает произвольный скопированный текст и извлекает:
    host, port, username, password.
    """
    if not text or not isinstance(text, str):
        return {}

    cleaned = text.strip()
    data: Dict[str, str] = {}

    # 1. Проверка формата ссылки: sftp://user:pass@host:port или ssh://...
    url_m = re.search(r'(?:sftp|ssh)://(?:([^:]+)(?::([^@]+))?@)?([^:/]+)(?::(\d+))?', cleaned, re.IGNORECASE)
    if url_m:
        user, pwd, host, port = url_m.groups()
        if host:
            data["host"] = host
        if port:
            data["port"] = port
        if user:
            data["username"] = user
        if pwd:
            data["password"] = pwd
        if data.get("host"):
            return data

    # 2. Построчный анализ (формат AmneziaVPN или Key: Value)
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]

    for i, line in enumerate(lines):
        lower = line.lower()

        # Формат с двоеточием: "Host: 201.10.73.198"
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip().lower()
            v = v.strip().strip("'\"")
            if any(h in k for h in ("host", "server", "ip", "хост", "сервер", "адрес")):
                data["host"] = v
            elif "port" in k or "порт" in k:
                port_digits = re.search(r'\d+', v)
                if port_digits:
                    data["port"] = port_digits.group(0)
            elif any(u in k for u in ("user", "login", "пользователь", "логин", "имя")):
                data["username"] = v
            elif any(p in k for p in ("pass", "пароль", "secret")):
                data["password"] = v
            elif any(d in k for d in ("path", "folder", "dir", "directory", "папка", "каталог")):
                data["folder"] = v

        # Формат AmneziaVPN (метка на одной строке, значение на следующей):
        # Host
        # 201.10.73.198
        elif i + 1 < len(lines):
            nxt = lines[i + 1].strip().strip("'\"")
            if lower in ("host", "server", "ip", "хост", "сервер"):
                data["host"] = nxt
            elif lower in ("port", "порт"):
                port_digits = re.search(r'\d+', nxt)
                if port_digits:
                    data["port"] = port_digits.group(0)
            elif lower in ("user name", "username", "user", "пользователь", "логин"):
                data["username"] = nxt
            elif lower in ("password", "pass", "пароль"):
                data["password"] = nxt
            elif lower in ("path", "folder", "dir", "directory", "папка", "каталог"):
                data["folder"] = nxt

    # 3. Дополнительный поиск IP адреса, если хост не найден
    if "host" not in data:
        ip_m = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', cleaned)
        if ip_m:
            data["host"] = ip_m.group(0)

    # 4. Если порт не найден явно, но в тексте есть порт
    if "port" not in data:
        port_m = re.search(r'\bport\s*[:=]?\s*(\d+)\b', cleaned, re.IGNORECASE)
        if port_m:
            data["port"] = port_m.group(1)

    return data
