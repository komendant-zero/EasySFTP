"""
Интеграционные тесты графического интерфейса EasySFTP.
Проверяют корректность инициализации окон, переключения экранов,
работы темы оформления и всех диалоговых окон.
"""

import unittest
import tkinter as tk
from ui.app import EasySFTPApp
from ui.help_window import HelpWindow
from ui.server_manager import ServerManagerDialog
from ui.permissions_dialog import PermissionsDialog
from ui.editor_window import EditorWindow
from ui.user_manager_window import UserManagerWindow
from core.server_user_manager import ServerUserManager


class TestUIFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()
        cls.app = EasySFTPApp(cls.root)
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app._on_close_app()
        except Exception:
            pass

    def test_screen_switching(self):
        self.app._show_screen("files")
        self.root.update()
        self.assertEqual(self.app.frame_files.winfo_manager(), "pack")
        self.assertEqual(self.app.frame_connect.winfo_manager(), "")

        self.app._show_screen("connect")
        self.root.update()
        self.assertEqual(self.app.frame_connect.winfo_manager(), "pack")
        self.assertEqual(self.app.frame_files.winfo_manager(), "")

    def test_theme_toggle(self):
        cur_theme = self.app.theme_mgr.theme_name
        new_theme = self.app._toggle_theme()
        self.root.update()
        self.assertNotEqual(cur_theme, new_theme)

        # Переключаем обратно
        restored = self.app._toggle_theme()
        self.root.update()
        self.assertEqual(restored, cur_theme)

    def test_help_window(self):
        w = HelpWindow(self.root, self.app.theme_mgr)
        self.root.update()
        self.assertIsNotNone(w.topic_listbox)
        w.destroy()
        self.root.update()

    def test_editor_window(self):
        w = EditorWindow(
            self.root,
            filename="demo.py",
            initial_content="def main():\n    return 42\n",
            theme_mgr=self.app.theme_mgr
        )
        self.root.update()
        self.assertIn("main", w.text.get("1.0", "end"))
        w.destroy()
        self.root.update()

    def test_permissions_dialog(self):
        w = PermissionsDialog(
            self.root,
            filename="config.json",
            initial_mode=0o644,
            is_dir=False,
            theme_mgr=self.app.theme_mgr,
            on_apply=lambda mode, rec: None
        )
        self.root.update()
        self.assertEqual(w.var_octal.get(), "644")
        w.destroy()
        self.root.update()

    def test_user_manager_window(self):
        mgr = ServerUserManager(self.app.demo_sftp, is_demo=True)
        w = UserManagerWindow(
            self.root,
            server_user_mgr=mgr,
            theme_mgr=self.app.theme_mgr,
            current_server_host="demo.local",
            current_server_port=22
        )
        self.root.update()
        self.assertIsNotNone(w.tree)
        w.destroy()
        self.root.update()

    def test_server_manager_dialog(self):
        w = ServerManagerDialog(
            self.root,
            config_mgr=self.app.config_mgr,
            theme_mgr=self.app.theme_mgr,
            on_connect=lambda s: None
        )
        self.root.update()
        self.assertIsNotNone(w.server_listbox)
        w.destroy()
        self.root.update()


if __name__ == "__main__":
    unittest.main()
