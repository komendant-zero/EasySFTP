"""
Пакет ядра EasySFTP: клиенты SFTP, локальной ФС, конфигурация и демо-сервер.
"""

from core.file_utils import FileItem, format_size, format_time, get_file_icon_and_type, is_text_file
from core.sftp_client import SFTPClient, CancelToken, translate_sftp_error
from core.local_client import LocalClient
from core.config_manager import ConfigManager
from core.demo_server import DemoSFTPClient

__all__ = [
    "FileItem",
    "format_size",
    "format_time",
    "get_file_icon_and_type",
    "is_text_file",
    "SFTPClient",
    "CancelToken",
    "translate_sftp_error",
    "LocalClient",
    "ConfigManager",
    "DemoSFTPClient",
]
