"""
EasySFTP — Простой, надёжный и понятный даже новичку SFTP-клиент.
Точка входа в приложение.
"""

import os
import sys
import tkinter as tk

# Добавляем корневую директорию проекта в sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ui.app import EasySFTPApp


def main():
    root = tk.Tk()
    app = EasySFTPApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
