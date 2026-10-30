"""
Интерактивное руководство и справочник для пользователя в EasySFTP.
Объяснение всех базовых понятий (SFTP, SSH, хост, порт 22, chmod, пути на Linux, песочница) простыми словами.
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, List

from ui.theme import ThemeManager


HELP_SECTIONS: Dict[str, str] = {
    "Что такое SFTP простыми словами": (
        "Что такое SFTP?\n"
        "SFTP (SSH File Transfer Protocol) — это безопасный способ работать с файлами "
        "на удалённом компьютере (сервере) точно так же, как на обычной флешке.\n\n"
        "Чем SFTP отличается от старого FTP?\n"
        "• Обычный FTP (порт 21) передаёт пароли и файлы в открытом виде — их может перехватить злоумышленник.\n"
        "• SFTP (порт 22) полностью шифрует всё соединение с помощью защищённого протокола SSH.\n\n"
        "В EasySFTP интерфейс сделан как в современном проводнике файлов: "
        "вы открываете папки, загружаете файлы одной кнопкой и редактируете код прямо на сервере!"
    ),
    "Где взять данные для подключения": (
        "Когда вы покупаете сервер на хостинге (например, Timeweb, Beget, Selectel, Hetzner, DigitalOcean) "
        "или настраиваете AmneziaVPN, вам выдаются данные доступа:\n\n"
        "1. Хост (IP-адрес сервера):\n"
        "   Это адрес вашего сервера (например: 185.120.45.67) или привязанный домен (mysite.ru).\n\n"
        "2. Порт:\n"
        "   Для SFTP всегда по умолчанию используется порт 22. В AmneziaVPN порт часто бывает 222 или 2222.\n\n"
        "3. Логин (Пользователь):\n"
        "   Главный администратор на Linux называется 'root'. На некоторых серверах логин может быть 'ubuntu', 'debian' или 'sftp_user'.\n\n"
        "4. Пароль или SSH-ключ:\n"
        "   • Если вам выдан пароль — выберите вкладку «Пароль» и вставьте его.\n"
        "   • Если используется ключ — выберите вкладку «SSH-ключ» и укажите файл (.pem, .key, id_rsa).\n\n"
        "Подсказка: Нажмите кнопку «Вставить из буфера обмена», и EasySFTP сам заполнит все поля!"
    ),
    "Умная вставка из AmneziaVPN и ссылок": (
        "EasySFTP поддерживает интеллектуальное распознавание настроек из буфера обмена:\n\n"
        "1. Из AmneziaVPN:\n"
        "   Скопируйте реквизиты контейнера SFTP в приложении AmneziaVPN и нажмите кнопку вставки в EasySFTP.\n\n"
        "2. Из SFTP/SSH URL ссылок:\n"
        "   Формат вида: sftp://user:password@1.2.3.4:222/path\n\n"
        "3. Из писем хостинга:\n"
        "   Скопируйте письмо с IP-адресом, логином и паролем — умный алгоритм автоматически найдёт все нужные данные!"
    ),
    "Как загружать, скачивать и удалять": (
        "Передача файлов в EasySFTP максимально упрощена:\n\n"
        "1. Загрузка на сервер (с компьютера на сервер):\n"
        "   • Нажмите верхнюю кнопку «Загрузить».\n"
        "   • Выберите один или несколько файлов на вашем ПК.\n"
        "   • Файлы сразу загрузятся в открытую папку на сервере!\n\n"
        "2. Скачивание на компьютер (с сервера на ваш ПК):\n"
        "   • Выделите нужный файл или папку в таблице.\n"
        "   • Нажмите кнопку «Скачать» (или двойной клик по файлу).\n"
        "   • Выберите папку на компьютере (по умолчанию открывается папка «Загрузки»).\n\n"
        "3. Передача целых папок:\n"
        "   EasySFTP умеет скачивать целые директории рекурсивно со всеми вложенными файлами и подпапками!"
    ),
    "Встроенный редактор файлов": (
        "Вам больше не нужно скачивать файл, открывать его в блокноте и загружать обратно!\n\n"
        "Как редактировать файл прямо на сервере:\n"
        "1. Дважды кликните по текстовому файлу (например: index.html, bot.py, .env, config.json).\n"
        "2. Откроется окно встроенного редактора с номерами строк и поиском по Ctrl+F.\n"
        "3. Внесите изменения в код или конфиг.\n"
        "4. Нажмите «Сохранить» или сочетание клавиш Ctrl+S.\n\n"
        "Изменения мгновенно сохранятся на удалённом сервере!"
    ),
    "Где лежат сайты и боты на Linux": (
        "На серверах Linux нет дисков C: и D:, файловая система начинается с корневой папки '/'.\n\n"
        "Популярные стандартные пути:\n"
        "• /var/www/html/ — стандартная папка для веб-сайтов (Nginx, Apache).\n"
        "• /home/имя_пользователя/ — домашняя папка пользователя (сюда обычно загружают ботов и скрипты).\n"
        "• /root/ — домашняя папка главного администратора root.\n"
        "• /etc/ — системные конфигурационные файлы (nginx, php, ssh).\n\n"
        "Подсказка: кнопка «Домой» быстро переводит вас в домашнюю папку пользователя, а «↑ Вверх» — на один уровень ближе к корню."
    ),
    "Права доступа (chmod 755, 644)": (
        "В Linux у каждого файла есть права для трёх категорий: Владелец, Группа и Все остальные.\n\n"
        "Что значат цифры:\n"
        "• 4 — Чтение (r)\n"
        "• 2 — Запись / изменение (w)\n"
        "• 1 — Выполнение как программа (x)\n\n"
        "Самые частые комбинации:\n"
        "• 644 (rw-r--r--) — стандарт для обычных файлов сайта (.html, .css, картинок). Владелец может изменять, остальные — только читать.\n"
        "• 755 (rwxr-xr-x) — стандарт для ПАПОК и запускаемых скриптов. Позволяет заходить в папку.\n"
        "• 600 (rw-------) — секретные файлы (пароли в .env, ключи SSH). Доступны только владельцу.\n\n"
        "В EasySFTP кликните правой кнопкой по файлу -> «Права доступа (chmod)», и вы сможете легко выставить права галочками или готовыми кнопками-пресетами."
    ),
    "Изолированные пользователи и песочница": (
        "Панель администратора «Пользователи» позволяет безопасно давать доступ клиентам или коллегам:\n\n"
        "1. Режим изолированной песочницы (Sandbox):\n"
        "   Пользователь имеет полный доступ на чтение, запись и удаление файлов внутри назначенных ему папок, "
        "но физически изолирован от остального сервера (chroot jail с bind mounts).\n\n"
        "2. Режим только для чтения (Read-Only):\n"
        "   Пользователь может только скачивать и просматривать файлы без права изменения.\n\n"
        "3. Назначение нескольких директорий (Multi-Directory):\n"
        "   Можно дать пользователю одновременный доступ к /website, /uploads и /data без раскрытия остальной системы."
    ),
    "Учебный сервер (Песочница)": (
        "У вас пока нет своего сервера или хотите безопасно потренироваться?\n\n"
        "Нажмите карточку «Демо-песочница» в левой панели серверов EasySFTP!\n\n"
        "Программа мгновенно запустит безопасный изолированный сервер-песочницу прямо на вашем компьютере "
        "с готовым учебным сайтом, скриптом Telegram-бота и инструкцией.\n\n"
        "Вы сможете тренироваться скачивать, загружать, удалять и редактировать файлы "
        "без интернета и без малейшего риска для реальных серверов!"
    ),
    "Решение частых проблем": (
        "1. 'Connection timed out' (Время ожидания истекло):\n"
        "   • Сервер выключен в панели управления хостингом.\n"
        "   • Опечатка в IP-адресе или порту.\n"
        "   • Брандмауэр хостинга блокирует входящие подключения на порт.\n\n"
        "2. 'Authentication failed' (Ошибка авторизации):\n"
        "   • Неверный логин или пароль.\n"
        "   • Скопирован пароль с лишним пробелом на конце.\n"
        "   • Указан неподходящий SSH-ключ.\n\n"
        "3. 'Permission denied' (Отказано в доступе):\n"
        "   • Текущий пользователь не имеет прав писать в системную папку /etc или корень /.\n"
        "   Решение: перейдите в домашнюю папку пользователя (например: /sftp_user или /home/user) или подключитесь под 'root'."
    )
}


class HelpWindow(tk.Toplevel):
    """
    Окно понятной интерактивной справки и руководства для пользователя.
    """
    def __init__(self, parent: tk.Tk, theme_mgr: ThemeManager):
        super().__init__(parent)
        self.theme_mgr = theme_mgr
        self.topic_keys = list(HELP_SECTIONS.keys())

        self.title("Справка — EasySFTP")
        self.geometry("860x560")
        self.minsize(720, 440)
        self.transient(parent)

        self._build_ui()
        self._center_window(parent)

    def _center_window(self, parent):
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() - 860) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - 560) // 2
            self.geometry(f"+{max(20, x)}+{max(20, y)}")
        except Exception:
            pass

    def _build_ui(self):
        c = self.theme_mgr.colors
        self.configure(bg=c["bg"])

        main_box = ttk.Frame(self, style="Main.TFrame")
        main_box.pack(fill="both", expand=True, padx=14, pady=14)

        # -------------------------------------------------------------
        # Левая колонка: Темы и поиск
        # -------------------------------------------------------------
        left_box = ttk.Frame(main_box, style="Card.TFrame", width=280, padding=12)
        left_box.pack(side="left", fill="both", padx=(0, 10))

        lbl_topics = ttk.Label(
            left_box,
            text="Разделы справки",
            font=(self.theme_mgr.display_font, 11, "bold")
        )
        lbl_topics.pack(anchor="w", pady=(0, 8))

        # Поиск по темам
        self.entry_search = ttk.Entry(left_box, font=(self.theme_mgr.ui_font, 9))
        self.entry_search.pack(fill="x", pady=(0, 8))
        self.entry_search.bind("<KeyRelease>", lambda e: self._filter_topics())

        self.topic_listbox = tk.Listbox(
            left_box,
            bg=c["surface_bg"],
            fg=c["fg"],
            selectbackground=c["accent"],
            selectforeground="#ffffff",
            font=(self.theme_mgr.ui_font, 9),
            relief="flat",
            borderwidth=1,
            highlightthickness=0,
            activestyle="none"
        )
        self.topic_listbox.pack(fill="both", expand=True)
        self.topic_listbox.bind("<<ListboxSelect>>", self._on_select_topic)

        self._populate_listbox(self.topic_keys)

        # -------------------------------------------------------------
        # Правая колонка: Содержимое статьи
        # -------------------------------------------------------------
        right_box = ttk.Frame(main_box, style="Card.TFrame", padding=16)
        right_box.pack(side="right", fill="both", expand=True)

        self.lbl_article_title = ttk.Label(
            right_box,
            text="",
            font=(self.theme_mgr.display_font, 12, "bold")
        )
        self.lbl_article_title.pack(anchor="w", pady=(0, 10))

        text_container = ttk.Frame(right_box, style="Card.TFrame")
        text_container.pack(fill="both", expand=True)

        self.text_content = tk.Text(
            text_container,
            wrap="word",
            font=(self.theme_mgr.ui_font, 10),
            bg=c["surface_bg"],
            fg=c["fg"],
            relief="flat",
            padx=12,
            pady=10,
            state="disabled",
            borderwidth=0,
            highlightthickness=0
        )
        self.text_content.pack(side="left", fill="both", expand=True)

        scroll_text = ttk.Scrollbar(text_container, orient="vertical", command=self.text_content.yview)
        self.text_content.configure(yscrollcommand=scroll_text.set)
        scroll_text.pack(side="right", fill="y")

        if self.topic_keys:
            self.topic_listbox.selection_set(0)
            self._show_topic(self.topic_keys[0])

    def _populate_listbox(self, keys: List[str]):
        self.topic_listbox.delete(0, tk.END)
        for key in keys:
            self.topic_listbox.insert(tk.END, key)

    def _filter_topics(self):
        query = self.entry_search.get().strip().lower()
        if not query:
            filtered = self.topic_keys
        else:
            filtered = [k for k in self.topic_keys if query in k.lower() or query in HELP_SECTIONS[k].lower()]
        self._populate_listbox(filtered)
        if filtered:
            self.topic_listbox.selection_set(0)
            self._show_topic(filtered[0])

    def _on_select_topic(self, event=None):
        sel = self.topic_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        visible_text = self.topic_listbox.get(idx)
        self._show_topic(visible_text)

    def _show_topic(self, key: str):
        content = HELP_SECTIONS.get(key, "")
        self.lbl_article_title.config(text=key)

        self.text_content.config(state="normal")
        self.text_content.delete("1.0", tk.END)
        self.text_content.insert("1.0", content)
        self.text_content.config(state="disabled")
