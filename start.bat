@echo off
chcp 65001 > nul
title EasySFTP — Запуск...

echo.
echo ========================================================
echo   EasySFTP — Простой и понятный SFTP-клиент
echo ========================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ОШИБКА] Python не найден в системе!
    echo Пожалуйста, установите Python с официального сайта https://www.python.org
    echo Обязательно отметьте галочку "Add Python to PATH" при установке.
    echo.
    pause
    exit /b 1
)

python main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ВНИМАНИЕ] Приложение завершилось с ошибкой.
    pause
)
