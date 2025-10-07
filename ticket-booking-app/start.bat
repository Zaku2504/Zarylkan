@echo off
echo ===============================================
echo        AirBook - Система бронирования билетов
echo ===============================================
echo.

echo Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не найден! Убедитесь, что Python установлен и добавлен в PATH.
    pause
    exit /b 1
)

echo Python найден!
echo.

echo Проверка виртуального окружения...
if not exist "venv" (
    echo Создание виртуального окружения...
    python -m venv venv
    if errorlevel 1 (
        echo ОШИБКА: Не удалось создать виртуальное окружение!
        pause
        exit /b 1
    )
    echo Виртуальное окружение создано!
)

echo Активация виртуального окружения...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ОШИБКА: Не удалось активировать виртуальное окружение!
    pause
    exit /b 1
)

echo Установка зависимостей...
pip install -r requirements.txt
if errorlevel 1 (
    echo ОШИБКА: Не удалось установить зависимости!
    pause
    exit /b 1
)

echo.
echo ===============================================
echo Запуск приложения AirBook...
echo ===============================================
echo.
echo Приложение будет доступно по адресу:
echo http://localhost:5000
echo.
echo Для входа используйте:
echo Администратор: admin / admin123
echo Или зарегистрируйте нового пользователя
echo.
echo Для остановки нажмите Ctrl+C
echo.

python app.py

pause