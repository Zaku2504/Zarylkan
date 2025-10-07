# Запуск AirBook - Система бронирования билетов

# Проверка Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python найден: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ОШИБКА: Python не найден! Убедитесь, что Python установлен и добавлен в PATH." -ForegroundColor Red
    Read-Host "Нажмите Enter для выхода"
    exit 1
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "    AirBook - Система бронирования билетов" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Проверка виртуального окружения
if (-not (Test-Path "venv")) {
    Write-Host "Создание виртуального окружения..." -ForegroundColor Yellow
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ОШИБКА: Не удалось создать виртуальное окружение!" -ForegroundColor Red
        Read-Host "Нажмите Enter для выхода"
        exit 1
    }
    Write-Host "Виртуальное окружение создано!" -ForegroundColor Green
}

# Активация виртуального окружения
Write-Host "Активация виртуального окружения..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ОШИБКА: Не удалось активировать виртуальное окружение!" -ForegroundColor Red
    Write-Host "Попробуйте запустить: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Yellow
    Read-Host "Нажмите Enter для выхода"
    exit 1
}

# Установка зависимостей
Write-Host "Установка зависимостей..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "ОШИБКА: Не удалось установить зависимости!" -ForegroundColor Red
    Read-Host "Нажмите Enter для выхода"
    exit 1
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "Запуск приложения AirBook..." -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Приложение будет доступно по адресу:" -ForegroundColor Cyan
Write-Host "http://localhost:5000" -ForegroundColor White -BackgroundColor Blue
Write-Host ""
Write-Host "Для входа используйте:" -ForegroundColor Yellow
Write-Host "Администратор: admin / admin123" -ForegroundColor White
Write-Host "Или зарегистрируйте нового пользователя" -ForegroundColor White
Write-Host ""
Write-Host "Для остановки нажмите Ctrl+C" -ForegroundColor Red
Write-Host ""

# Запуск приложения
python app.py

Read-Host "Нажмите Enter для выхода"