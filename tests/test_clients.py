"""
Тесты файловых клиентов: локального и учебного демо-сервера.
"""

import os
import tempfile
import unittest
from core.local_client import LocalClient
from core.demo_server import DemoSFTPClient


class TestClients(unittest.TestCase):
    def setUp(self):
        self.temp_local = tempfile.mkdtemp()
        self.temp_demo = tempfile.mkdtemp()

        self.local = LocalClient(self.temp_local)
        self.demo = DemoSFTPClient(self.temp_demo)
        self.demo.connect()

    def tearDown(self):
        self.demo.disconnect()
        import shutil
        shutil.rmtree(self.temp_local, ignore_errors=True)
        shutil.rmtree(self.temp_demo, ignore_errors=True)

    def test_local_operations(self):
        # Создание папки
        new_dir = os.path.join(self.temp_local, "subfolder")
        self.local.create_directory(new_dir)
        self.assertTrue(os.path.isdir(new_dir))

        # Навигация
        self.local.cd(new_dir)
        self.assertEqual(os.path.abspath(self.local.pwd()), os.path.abspath(new_dir))
        self.local.cd("..")
        self.assertEqual(os.path.abspath(self.local.pwd()), os.path.abspath(self.temp_local))

        # Создание и удаление файла
        test_file = os.path.join(self.temp_local, "sample.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("content")
        items = self.local.list_dir()
        self.assertTrue(any(it.name == "sample.txt" for it in items))

        self.local.delete_file(test_file)
        self.assertFalse(os.path.exists(test_file))

    def test_demo_sftp_operations(self):
        # Проверка начальных учебных файлов
        items = self.demo.list_dir("/")
        item_names = [it.name for it in items]
        self.assertTrue(any("index.html" in self.demo.read_text_file(f"/{it.name}") if not it.is_dir else True for it in items))

        # Чтение и запись текста
        self.demo.write_text_file("/test_edit.txt", "Новый текст для проверки")
        content = self.demo.read_text_file("/test_edit.txt")
        self.assertEqual(content, "Новый текст для проверки")

        # Передача файлов между локальным клиентом и демо-сервером
        local_upload_file = os.path.join(self.temp_local, "to_upload.txt")
        with open(local_upload_file, "w", encoding="utf-8") as f:
            f.write("Файл с моего компьютера")

        # Загрузка на демо-сервер
        self.demo.upload_file(local_upload_file, "/uploaded.txt")
        self.assertEqual(self.demo.read_text_file("/uploaded.txt"), "Файл с моего компьютера")

        # Скачивание с демо-сервера на ПК
        local_download_file = os.path.join(self.temp_local, "downloaded.txt")
        self.demo.download_file("/uploaded.txt", local_download_file)
        self.assertTrue(os.path.exists(local_download_file))
        with open(local_download_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Файл с моего компьютера")

    def test_directory_renaming(self):
        # 1. Проверка переименования папки в демо-сервере
        self.demo.create_directory("/projects")
        self.demo.write_text_file("/projects/readme.txt", "Project documentation")
        
        # Переименование директории
        self.demo.rename("/projects", "/cool_projects")
        
        items = self.demo.list_dir("/")
        item_names = [it.name for it in items]
        self.assertIn("cool_projects", item_names)
        self.assertNotIn("projects", item_names)
        self.assertEqual(self.demo.read_text_file("/cool_projects/readme.txt"), "Project documentation")

        # Переименование с завершающими слэшами
        self.demo.rename("/cool_projects/", "/final_projects/")
        items = self.demo.list_dir("/")
        item_names = [it.name for it in items]
        self.assertIn("final_projects", item_names)
        self.assertNotIn("cool_projects", item_names)

        # 2. Проверка переименования локальной директории
        local_dir1 = os.path.join(self.temp_local, "local_dir_old")
        local_dir2 = os.path.join(self.temp_local, "local_dir_new")
        self.local.create_directory(local_dir1)
        self.assertTrue(os.path.isdir(local_dir1))
        self.local.rename(local_dir1, local_dir2)
        self.assertFalse(os.path.exists(local_dir1))
        self.assertTrue(os.path.isdir(local_dir2))


if __name__ == "__main__":
    unittest.main()
