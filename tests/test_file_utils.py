"""
Тесты утилит работы с файлами и форматирования.
"""

import unittest
from core.file_utils import (
    format_size,
    format_time,
    get_file_icon_and_type,
    is_text_file,
    parse_mode_to_octal,
    parse_mode_to_rwx,
    FileItem
)


class TestFileUtils(unittest.TestCase):
    def test_format_size(self):
        self.assertEqual(format_size(0), "0 Б")
        self.assertEqual(format_size(500), "500 Б")
        self.assertIn("КБ", format_size(1024))
        self.assertIn("МБ", format_size(1024 * 1024))
        self.assertIn("ГБ", format_size(1024 * 1024 * 1024))
        self.assertEqual(format_size(-1), "—")
        self.assertEqual(format_size(None), "—")

    def test_file_type_and_icons(self):
        icon, desc = get_file_icon_and_type("test.html", False)
        self.assertEqual(icon, "💻")
        self.assertIn("HTML", desc)

        icon, desc = get_file_icon_and_type("photo.png", False)
        self.assertEqual(icon, "🖼️")

        icon, desc = get_file_icon_and_type("backup.zip", False)
        self.assertEqual(icon, "📦")

        icon, desc = get_file_icon_and_type("my_folder", True)
        self.assertEqual(icon, "📁")
        self.assertIn("Папка", desc)

    def test_is_text_file(self):
        self.assertTrue(is_text_file("index.html"))
        self.assertTrue(is_text_file(".env"))
        self.assertTrue(is_text_file("server.py"))
        self.assertTrue(is_text_file("config.json"))
        self.assertFalse(is_text_file("image.png"))
        self.assertFalse(is_text_file("archive.zip"))

    def test_parse_mode(self):
        self.assertEqual(parse_mode_to_octal(0o755), "755")
        self.assertEqual(parse_mode_to_octal(0o644), "644")
        self.assertEqual(parse_mode_to_octal(0o600), "600")

    def test_file_item_properties(self):
        item = FileItem(
            name="test.txt",
            path="/home/test.txt",
            size=2048,
            mtime=1700000000,
            is_dir=False,
            mode=0o644
        )
        self.assertIn("КБ", item.formatted_size)
        self.assertEqual(item.permissions_octal, "644")
        self.assertEqual(item.icon, "📝")


if __name__ == "__main__":
    unittest.main()
