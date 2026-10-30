"""
Тесты менеджера конфигураций и закладок серверов.
"""

import os
import tempfile
import unittest
from core.config_manager import ConfigManager


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
        self.mgr = ConfigManager(self.config_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_and_get_server(self):
        sid = self.mgr.add_or_update_server(
            name="Мой VDS",
            host="192.168.1.100",
            port=22,
            username="root",
            password="secret_password"
        )
        self.assertTrue(sid)
        servers = self.mgr.get_servers()
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0]["name"], "Мой VDS")
        self.assertEqual(servers[0]["host"], "192.168.1.100")
        self.assertEqual(servers[0]["password"], "secret_password")

        # Проверяем, что в самом файле пароль не лежит открытым текстом
        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = f.read()
            self.assertNotIn("secret_password", raw)

    def test_delete_server(self):
        sid = self.mgr.add_or_update_server(
            name="Сервер для удаления",
            host="10.0.0.1"
        )
        self.assertEqual(len(self.mgr.get_servers()), 1)
        self.mgr.delete_server(sid)
        self.assertEqual(len(self.mgr.get_servers()), 0)

    def test_last_connection_and_settings(self):
        self.mgr.set_last_connection(
            host="example.com",
            port=2222,
            username="ubuntu",
            password="123"
        )
        last = self.mgr.get_last_connection()
        self.assertEqual(last["host"], "example.com")
        self.assertEqual(last["port"], 2222)
        self.assertEqual(last["username"], "ubuntu")

        self.mgr.set_setting("theme", "light")
        self.assertEqual(self.mgr.get_setting("theme"), "light")


if __name__ == "__main__":
    unittest.main()
