"""
Тесты умного парсера настроек из буфера обмена.
"""

import unittest
from core.clipboard_parser import parse_sftp_clipboard


class TestClipboardParser(unittest.TestCase):
    def test_amnezia_format(self):
        amnezia_text = """
        Host
        201.10.73.198
        Port
        222
        User name
        sftp_user
        Password
        U9PpM82DZCJ1BUgh
        """
        res = parse_sftp_clipboard(amnezia_text)
        self.assertEqual(res.get("host"), "201.10.73.198")
        self.assertEqual(res.get("port"), "222")
        self.assertEqual(res.get("username"), "sftp_user")
        self.assertEqual(res.get("password"), "U9PpM82DZCJ1BUgh")

    def test_colon_format(self):
        text = "Host: 185.120.45.67\nPort: 22\nUser: root\nPassword: mysecretpassword"
        res = parse_sftp_clipboard(text)
        self.assertEqual(res.get("host"), "185.120.45.67")
        self.assertEqual(res.get("port"), "22")
        self.assertEqual(res.get("username"), "root")
        self.assertEqual(res.get("password"), "mysecretpassword")

    def test_url_format(self):
        url = "sftp://sftp_user:mypass@201.10.73.198:222"
        res = parse_sftp_clipboard(url)
        self.assertEqual(res.get("host"), "201.10.73.198")
        self.assertEqual(res.get("port"), "222")
        self.assertEqual(res.get("username"), "sftp_user")
        self.assertEqual(res.get("password"), "mypass")


if __name__ == "__main__":
    unittest.main()
