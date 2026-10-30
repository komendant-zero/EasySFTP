' Запуск EasySFTP в фоновом режиме без окна консоли
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw main.py", 0, False
