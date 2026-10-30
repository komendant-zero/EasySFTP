"""
Тесты менеджера пользователей, доступа к нескольким папкам и режима песочницы.
"""

import unittest
from core.server_user_manager import ServerUserManager, ManagedUser, generate_secure_password
from core.demo_server import DemoSFTPClient


class TestServerUserManager(unittest.TestCase):
    def test_password_generator(self):
        pwd = generate_secure_password(16)
        self.assertEqual(len(pwd), 16)
        self.assertTrue(any(c.isupper() for c in pwd))
        self.assertTrue(any(c.islower() for c in pwd))
        self.assertTrue(any(c.isdigit() for c in pwd))

    def test_multi_directory_creation(self):
        demo = DemoSFTPClient()
        demo.connect()
        mgr = ServerUserManager(demo, is_demo=True)

        ok, msg = mgr.create_user(
            username="dev_team",
            password="SecurePass123!",
            allowed_directories=["/website", "/scripts"],
            mode="sandbox"
        )
        self.assertTrue(ok)

        users = mgr.get_users()
        u = next(x for x in users if x.username == "dev_team")
        self.assertEqual(u.allowed_directories, ["/website", "/scripts"])
        self.assertEqual(u.mode, "sandbox")
        self.assertIn("Песочница", u.mode_badge)

        # Проверяем генерацию Linux скрипта настройки с bind mounts
        script = mgr.generate_linux_setup_script(u)
        self.assertIn("mount --bind \"/website\"", script)
        self.assertIn("mount --bind \"/scripts\"", script)
        self.assertIn("Match User dev_team", script)
        self.assertIn("ChrootDirectory /var/sftp/dev_team", script)

    def test_demo_user_sandbox_and_multi_dir_navigation(self):
        demo = DemoSFTPClient()
        demo.connect()

        # Регистрируем пользователя с песочницей и доступом к 2 папкам
        user_sandbox = ManagedUser(
            username="sandbox_user",
            password="123",
            allowed_directories=["/website", "/scripts"],
            mode="sandbox"
        )
        demo.add_demo_user(user_sandbox)

        # Входим под sandbox_user
        demo.connect(username="sandbox_user", password="123")
        self.assertEqual(demo.pwd(), "/")

        # В корне видны только разрешённые папки!
        root_items = demo.list_dir("/")
        names = [it.name for it in root_items]
        self.assertIn("website", names)
        self.assertIn("scripts", names)
        self.assertNotIn("ПРОЧИТАЙ_МЕНЯ.txt", names)  # Системный файл за пределами папок скрыт!

        # Входим в разрешённую папку /website
        demo.cd("/website")
        self.assertEqual(demo.pwd(), "/website")

        # В режиме песочницы: пользователь может свободно создавать и менять файлы внутри /website!
        demo.create_directory("/website/sub_sandbox")
        sub_items = demo.list_dir("/website")
        self.assertTrue(any(it.name == "sub_sandbox" for it in sub_items))

        demo.write_text_file("/website/test_sandbox.txt", "Hello sandbox")
        self.assertEqual(demo.read_text_file("/website/test_sandbox.txt"), "Hello sandbox")

        demo.delete_file("/website/test_sandbox.txt")

        # Но попытка выйти за пределы разрешённых папок блокируется!
        with self.assertRaises(PermissionError):
            demo.cd("/non_allowed_system_folder")


if __name__ == "__main__":
    unittest.main()
