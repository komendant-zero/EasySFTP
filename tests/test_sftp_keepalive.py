"""
Модульные тесты бесконечного подключения (Keepalive, авто-переподключение)
и переименования директорий в SFTPClient.
"""

import unittest
from unittest.mock import MagicMock, patch
import socket
import paramiko

from core.sftp_client import SFTPClient


class TestSFTPKeepAliveAndRename(unittest.TestCase):
    def setUp(self):
        self.client = SFTPClient()

    def tearDown(self):
        self.client.disconnect()

    @patch("paramiko.SSHClient")
    def test_connect_enables_keepalive(self, mock_ssh_cls):
        mock_ssh = MagicMock()
        mock_transport = MagicMock()
        mock_sock = MagicMock()
        mock_sftp = MagicMock()

        mock_ssh_cls.return_value = mock_ssh
        mock_ssh.get_transport.return_value = mock_transport
        mock_transport.sock = mock_sock
        mock_transport.is_active.return_value = True
        mock_ssh.open_sftp.return_value = mock_sftp

        # Мокируем поиск доступной директории
        with patch.object(self.client, "_discover_accessible_directory", return_value="/home/user"):
            res = self.client.connect(host="1.2.3.4", port=22, username="user", password="pwd")

        self.assertEqual(res, "/home/user")
        self.assertTrue(self.client.is_connected())

        # Проверяем, что Keepalive включён на уровне SSH Transport
        mock_transport.set_keepalive.assert_called_with(10)

        # Проверяем, что TCP Keepalive включён на уровне сокета
        mock_sock.setsockopt.assert_any_call(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

        # Проверяем, что watchdog запущен
        self.assertIsNotNone(self.client._watchdog_thread)
        self.assertTrue(self.client._watchdog_thread.is_alive())

    def test_rename_directory_logic(self):
        # Мокируем активное соединение
        self.client.ssh = MagicMock()
        self.client.sftp = MagicMock()
        self.client.current_path = "/var/www/my_site"
        self.client._manual_disconnect = False

        # Переименование директории
        self.client.rename("/var/www/my_site/", "/var/www/awesome_site/")
        self.client.sftp.rename.assert_called_with("/var/www/my_site", "/var/www/awesome_site")
        self.assertEqual(self.client.current_path, "/var/www/awesome_site")

    def test_auto_reconnect_retry_on_network_drop(self):
        self.client.ssh = MagicMock()
        self.client.sftp = MagicMock()
        self.client._last_connect_args = {
            "host": "test.server",
            "port": 22,
            "username": "user",
            "password": "pwd",
            "key_filename": None,
            "passphrase": None,
            "initial_dir": "/data",
            "timeout": 15
        }
        self.client._manual_disconnect = False

        # Первый вызов mkdir выбрасывает EOFError (разрыв сокета), второй успешен после reconnect
        call_count = 0
        def side_effect_mkdir(p):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise EOFError("Connection dropped by remote host")
            return None

        self.client.sftp.stat.side_effect = IOError("Not found")
        self.client.sftp.mkdir.side_effect = side_effect_mkdir

        # Мокируем переподключение
        reconnect_called = False
        def fake_reconnect():
            nonlocal reconnect_called
            reconnect_called = True
            return True

        self.client._reconnect = fake_reconnect

        # Создание директории должно завершиться успехом благодаря повторной попытке
        self.client.create_directory("/data/new_dir")
        self.assertTrue(reconnect_called)


if __name__ == "__main__":
    unittest.main()
