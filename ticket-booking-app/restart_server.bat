@echo off
echo ========================================
echo        ПЕРЕЗАПУСК FLASK СЕРВЕРА
echo ========================================

cd /d "c:\Users\Муса\OneDrive\Desktop\new shit\ticket-booking-app"

echo Останавливаем все процессы Python...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM python3.exe 2>nul
taskkill /F /IM python3.13.exe 2>nul

echo Ждем 2 секунды...
timeout /t 2 /nobreak >nul

echo.
echo Запускаем сервер заново...
echo Сервер будет доступен по адресу: http://127.0.0.1:5000
echo Для остановки нажмите Ctrl+C
echo.

python app.py

pause