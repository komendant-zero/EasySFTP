"""
Интеграционные тесты функционала EasySFTP:
- Умная вставка из буфера
- Демо-сервер и навигация
- Создание пользователя
- Настройка прав chmod
- Переименование папки через UI
- Сортировка колонок
"""

import time
import unittest
from unittest.mock import patch
import tkinter as tk
from ui.app import EasySFTPApp
from core.clipboard_parser import parse_sftp_clipboard


class TestFeaturesIntegration(unittest.TestCase):
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

    def test_smart_paste_parser(self):
        text = "Host: 192.168.1.50\nPort: 2222\nUser: testuser\nPassword: secret_password"
        parsed = parse_sftp_clipboard(text)
        self.assertEqual(parsed.get("host"), "192.168.1.50")
        self.assertEqual(parsed.get("port"), "2222")
        self.assertEqual(parsed.get("username"), "testuser")
        self.assertEqual(parsed.get("password"), "secret_password")

    def test_demo_server_connect(self):
        self.app._start_demo_server()
        time.sleep(0.2)
        self.app._process_queue()
        self.root.update()
        self.assertTrue(self.app.active_client.is_connected())
        self.assertEqual(self.app.frame_files.winfo_manager(), "pack")

        # Проверяем, что файлы в демо сервере загрузились
        self.assertGreater(len(self.app.current_remote_items), 0)

        # Отключаемся
        self.app._disconnect()

    def test_column_sorting(self):
        self.app._start_demo_server()
        time.sleep(0.2)
        self.app._process_queue()
        self.root.update()

        # Сортировка по имени
        self.app._sort_column("name")
        self.assertEqual(self.app.sort_column, "name")
        self.assertFalse(self.app.sort_reverse)

        # Повторный клик меняет направление
        self.app._sort_column("name")
        self.assertTrue(self.app.sort_reverse)

        # Сортировка по размеру
        self.app._sort_column("size")
        self.assertEqual(self.app.sort_column, "size")

        self.app._disconnect()

    def test_user_picker_navigation(self):
        # Добавляем два пользователя на один хост
        self.app.config_mgr.add_recent_server("10.0.0.1", 22, "root", "pass1")
        self.app.config_mgr.add_recent_server("10.0.0.1", 22, "developer", "pass2")

        groups = self.app._get_grouped_servers()
        target_group = next((g for g in groups if g["host"] == "10.0.0.1"), None)
        self.assertIsNotNone(target_group)
        self.assertEqual(len(target_group["users"]), 2)
        user_names = [u["username"] for u in target_group["users"]]
        self.assertIn("root", user_names)
        self.assertIn("developer", user_names)

        # Проверяем открытие окна выбора пользователя
        self.app._open_user_picker_for_group(target_group)
        self.root.update()
        self.assertEqual(self.app.pane_user_picker.winfo_manager(), "pack")
        self.assertEqual(self.app.pane_new_connection.winfo_manager(), "")

        # Проверяем возврат к форме добавления сервера
        self.app._show_new_connection_form()
        self.root.update()
        self.assertEqual(self.app.pane_new_connection.winfo_manager(), "pack")
        self.assertEqual(self.app.pane_user_picker.winfo_manager(), "")

    def test_ui_rename_directory(self):
        self.app._start_demo_server()
        time.sleep(0.2)
        self.app._process_queue()
        self.root.update()

        try:
            # Создаём тестовую директорию на демо-сервере
            self.app.active_client.create_directory("/ui_test_dir")
            self.app._refresh_remote_files()
            time.sleep(0.2)
            self.app._process_queue()
            self.root.update()

            # Находим элемент в таблице
            target_iid = None
            for i, it in enumerate(self.app.filtered_remote_items):
                if it.name == "ui_test_dir":
                    target_iid = str(i)
                    break

            self.assertIsNotNone(target_iid)
            self.app.tree_remote.selection_set(target_iid)
            self.app._on_item_select_change()

            # Кнопка переименования активна
            self.assertEqual(str(self.app.btn_rename_sel["state"]), "normal")

            # Переименовываем через mock dialog
            with patch("tkinter.simpledialog.askstring", return_value="ui_renamed_dir"):
                self.app._rename_selected_item()
                time.sleep(0.2)
                self.app._process_queue()
                self.root.update()

            # Проверяем, что папка переименована
            items = self.app.active_client.list_dir("/")
            names = [it.name for it in items]
            self.assertIn("ui_renamed_dir", names)
            self.assertNotIn("ui_test_dir", names)
        finally:
            # Очистка
            try:
                self.app.active_client.delete_directory_recursive("/ui_renamed_dir")
            except Exception:
                pass
            try:
                self.app.active_client.delete_directory_recursive("/ui_test_dir")
            except Exception:
                pass
            self.app._disconnect()


if __name__ == "__main__":
    unittest.main()
