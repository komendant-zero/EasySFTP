"""
Управление пользователями SFTP-сервера, правами доступа, мульти-директориями и режимом песочницы.
Поддерживает управление реальным Linux SSH/SFTP сервером и учебным демо-сервером.
"""

from __future__ import annotations
import json
import os
import posixpath
import random
import string
import time
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple, Any

from core.file_utils import get_app_data_dir


@dataclass
class ManagedUser:
    """Модель пользователя SFTP сервера с правами, набором папок и режимом песочницы."""
    username: str
    password: str
    allowed_directories: List[str] = field(default_factory=lambda: ["/"])  # Доступ к нескольким папкам!
    mode: str = "sandbox"  # "sandbox" (песочница), "read_write" (полный), "read_only" (только чтение)
    created_at: float = field(default_factory=time.time)
    description: str = ""

    # Для обратной совместимости
    @property
    def jail_directory(self) -> str:
        return self.allowed_directories[0] if self.allowed_directories else "/"

    @property
    def mode_display(self) -> str:
        if self.mode == "sandbox":
            return "🛡️ Песочница (Полная свобода внутри своих папок)"
        elif self.mode == "read_only":
            return "👁️ Только чтение (Read-Only)"
        return "✏️ Чтение и Запись"

    @property
    def mode_badge(self) -> str:
        if self.mode == "sandbox":
            return "🛡️ Песочница"
        elif self.mode == "read_only":
            return "👁️ Только чтение"
        return "🟢 Полный"


def generate_secure_password(length: int = 14) -> str:
    """Генерирует надёжный пароль из букв, цифр и безопасных спецсимволов."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice("!@#$%^&*")
    ]
    pwd += [random.choice(chars) for _ in range(length - 4)]
    random.shuffle(pwd)
    return "".join(pwd)


class ServerUserManager:
    """
    Менеджер пользователей SFTP сервера.
    Настраивает доступ к нескольким директориям, права и режим изолированной песочницы.
    """
    def __init__(self, sftp_client: Any = None, is_demo: bool = False):
        self.sftp_client = sftp_client
        self.is_demo = is_demo
        self.local_storage_path = os.path.join(get_app_data_dir(), "server_users.json")
        self.users: List[ManagedUser] = []
        self.load_local_users()

    def load_local_users(self):
        """Загружает сохранённый список пользователей для текущего сервера."""
        if os.path.exists(self.local_storage_path):
            try:
                with open(self.local_storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    host = getattr(self.sftp_client, "current_host", "default")
                    server_users = data.get(host, [])
                    self.users = []
                    for u in server_users:
                        # Поддержка старого формата jail_directory
                        dirs = u.get("allowed_directories")
                        if not dirs:
                            old_jail = u.get("jail_directory", "/")
                            dirs = [old_jail] if old_jail else ["/"]

                        mode = u.get("mode")
                        if not mode:
                            perm = u.get("permission", "read_write")
                            mode = "read_only" if perm == "read_only" else "sandbox"

                        self.users.append(ManagedUser(
                            username=u["username"],
                            password=u.get("password", ""),
                            allowed_directories=dirs,
                            mode=mode,
                            created_at=u.get("created_at", time.time()),
                            description=u.get("description", "")
                        ))
            except Exception:
                self.users = []

    def save_local_users(self):
        """Сохраняет список созданных пользователей."""
        host = getattr(self.sftp_client, "current_host", "default")
        data = {}
        if os.path.exists(self.local_storage_path):
            try:
                with open(self.local_storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        data[host] = [asdict(u) for u in self.users]
        try:
            with open(self.local_storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_users(self) -> List[ManagedUser]:
        return list(self.users)

    def generate_linux_setup_script(self, user: ManagedUser) -> str:
        """
        Генерирует надёжный bash-скрипт настройки OpenSSH в Linux:
        - Создаёт изолированное chroot окружение в /var/sftp/{username}
        - Монтирует несколько указанных директорий через mount --bind (с fstab)
        - Если режим Sandbox: даёт 100% права внутри привязанных папок, но блокирует доступ к серверу
        - Если режим Read-Only: монтирует в режиме только чтение
        """
        chroot_root = f"/var/sftp/{user.username}"
        is_ro = (user.mode == "read_only")
        ro_flag = "ro" if is_ro else "rw"

        mount_commands = []
        for d in user.allowed_directories:
            clean_dir = posixpath.normpath(d.strip())
            folder_name = posixpath.basename(clean_dir.rstrip("/")) or "root_files"
            target_mount = f"{chroot_root}/{folder_name}"

            mount_cmd = f"""
# Подключение папки: {clean_dir} -> {target_mount}
mkdir -p "{clean_dir}"
mkdir -p "{target_mount}"
# Монтирование через bind
if ! mountpoint -q "{target_mount}"; then
    mount --bind "{clean_dir}" "{target_mount}"
fi
"""
            if is_ro:
                mount_cmd += f"""mount -o remount,ro,bind "{target_mount}"\n"""
            else:
                mount_cmd += f"""
# Режим песочницы: полный карт-бланш для пользователя внутри папки
chown -R {user.username}:sftpusers "{clean_dir}"
chmod -R 775 "{clean_dir}"
"""

            # Автомонтирование при перезагрузке
            mount_cmd += f"""
if ! grep -q "{target_mount}" /etc/fstab; then
    echo "{clean_dir} {target_mount} none bind,{ro_flag} 0 0" >> /etc/fstab
fi
"""
            mount_commands.append(mount_cmd)

        mount_script_block = "\n".join(mount_commands)

        script = f"""#!/bin/bash
# ==============================================================================
# Настройка пользователя SFTP: {user.username}
# Режим: {user.mode_display}
# Папки: {', '.join(user.allowed_directories)}
# ==============================================================================
set -e

# 1. Создание изолированной группы sftpusers
groupadd -f sftpusers

# 2. Создание пользователя без shell-доступа (только SFTP)
if id "{user.username}" &>/dev/null; then
    echo "Пользователь {user.username} уже существует, обновляем группу..."
    usermod -g sftpusers -s /bin/false "{user.username}"
else
    useradd -M -s /bin/false -g sftpusers "{user.username}"
fi

# 3. Установка пароля
echo "{user.username}:{user.password}" | chpasswd

# 4. Создание корневой папки Chroot (должна принадлежать root:root с правами 755)
mkdir -p "{chroot_root}"
chown root:root "{chroot_root}"
chmod 755 "{chroot_root}"

# 5. Привязка разрешённых директорий (Multi-Directory Bind Mounts)
{mount_script_block}

# 6. Настройка OpenSSH Chroot (/etc/ssh/sshd_config)
SSHD_CONFIG="/etc/ssh/sshd_config"
MATCH_BLOCK="Match User {user.username}"

if ! grep -q "$MATCH_BLOCK" "$SSHD_CONFIG"; then
    cat << 'EOF' >> "$SSHD_CONFIG"

Match User {user.username}
    ChrootDirectory {chroot_root}
    ForceCommand internal-sftp
    AllowTcpForwarding no
    X11Forwarding no
EOF
fi

# 7. Проверка конфигурации и перезапуск SSH
if sshd -t; then
    systemctl restart sshd || systemctl restart ssh || service ssh restart || true
    echo "✓ Пользователь {user.username} успешно настроен и изолирован в песочнице!"
else
    echo "Ошибка синтаксиса sshd_config. Проверьте конфигурацию!" >&2
    exit 1
fi
"""
        return script

    def create_user(
        self,
        username: str,
        password: str,
        allowed_directories: List[str],
        mode: str = "sandbox",
        description: str = ""
    ) -> Tuple[bool, str]:
        """
        Создаёт пользователя на сервере с доступом к нескольким папкам и режимом песочницы.
        """
        username = username.strip()
        if not username:
            return False, "Имя пользователя не может быть пустым."

        clean_dirs = [posixpath.normpath(d.strip()) for d in allowed_directories if d.strip()]
        if not clean_dirs:
            clean_dirs = ["/"]

        new_user = ManagedUser(
            username=username,
            password=password,
            allowed_directories=clean_dirs,
            mode=mode,
            created_at=time.time(),
            description=description
        )

        # 1. Если это Демо-сервер
        if self.is_demo:
            if hasattr(self.sftp_client, "add_demo_user"):
                self.sftp_client.add_demo_user(new_user)
            self._add_or_replace_user(new_user)
            self.save_local_users()
            dirs_str = ", ".join(clean_dirs)
            return True, f"Пользователь '{username}' создан в учебной песочнице!\nДоступные папки: {dirs_str}\nРежим: {new_user.mode_display}"

        # 2. Если подключены к реальному серверу
        ssh_client = getattr(self.sftp_client, "ssh", None)
        if ssh_client:
            try:
                script = self.generate_linux_setup_script(new_user)
                stdin, stdout, stderr = ssh_client.exec_command(f"bash -c '{script}'", timeout=20)
                exit_status = stdout.channel.recv_exit_status()

                if exit_status == 0:
                    self._add_or_replace_user(new_user)
                    self.save_local_users()
                    dirs_str = ", ".join(clean_dirs)
                    return True, f"Пользователь '{username}' успешно настроен на сервере!\nПапки: {dirs_str}\nРежим: {new_user.mode_display}"
                else:
                    self._add_or_replace_user(new_user)
                    self.save_local_users()
                    return True, (
                        f"Пользователь '{username}' сохранён в программе!\n\n"
                        f"Примечание: на сервере требуются права root для автомонтирования папок.\n"
                        f"Используйте кнопку 'Копировать Linux-скрипт', чтобы запустить его под root."
                    )
            except Exception:
                self._add_or_replace_user(new_user)
                self.save_local_users()
                return True, f"Пользователь '{username}' сохранён. Готовый Linux-скрипт можно скопировать из карточки пользователя."

        self._add_or_replace_user(new_user)
        self.save_local_users()
        return True, f"Пользователь '{username}' успешно сохранён."

    def delete_user(self, username: str) -> Tuple[bool, str]:
        """Удаляет пользователя."""
        self.users = [u for u in self.users if u.username != username]
        self.save_local_users()

        ssh_client = getattr(self.sftp_client, "ssh", None)
        if ssh_client and not self.is_demo:
            try:
                cmd = f"userdel -r '{username}' 2>/dev/null || true"
                ssh_client.exec_command(cmd, timeout=5)
            except Exception:
                pass

        return True, f"Пользователь '{username}' удалён."

    def _add_or_replace_user(self, user: ManagedUser):
        self.users = [u for u in self.users if u.username != user.username]
        self.users.append(user)
