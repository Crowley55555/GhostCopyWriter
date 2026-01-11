# PowerShell скрипт для настройки автоматической очистки токенов через Task Scheduler (Windows)
# Использование: PowerShell -ExecutionPolicy Bypass -File setup_task_scheduler.ps1

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Настройка автоматической очистки токенов" -ForegroundColor Cyan
Write-Host "Windows Task Scheduler" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Получаем текущую директорию проекта
$ProjectDir = Get-Location
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Path

if (-not $PythonPath) {
    $PythonPath = (Get-Command py -ErrorAction SilentlyContinue).Path
}

if (-not $PythonPath) {
    Write-Host "❌ Ошибка: Python не найден в PATH" -ForegroundColor Red
    Write-Host "Установите Python или добавьте его в PATH" -ForegroundColor Red
    exit 1
}

Write-Host "Директория проекта: $ProjectDir" -ForegroundColor Green
Write-Host "Python путь: $PythonPath" -ForegroundColor Green
Write-Host ""

# Проверяем наличие manage.py
if (-not (Test-Path "$ProjectDir\manage.py")) {
    Write-Host "❌ Ошибка: manage.py не найден в текущей директории" -ForegroundColor Red
    Write-Host "Запустите скрипт из корня проекта Ghostwriter" -ForegroundColor Red
    exit 1
}

Write-Host "✅ manage.py найден" -ForegroundColor Green
Write-Host ""

# Создаем директорию для логов
$LogsDir = "$ProjectDir\logs"
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir | Out-Null
    Write-Host "✅ Директория для логов создана: $LogsDir" -ForegroundColor Green
} else {
    Write-Host "✅ Директория для логов существует: $LogsDir" -ForegroundColor Green
}
Write-Host ""

# Создаем bat-файл для запуска команды очистки
$CleanupBat = "$ProjectDir\cleanup_tokens.bat"
$CleanupDeleteBat = "$ProjectDir\cleanup_tokens_delete.bat"

# Bat-файл для деактивации
@"
@echo off
cd /d "$ProjectDir"
"$PythonPath" manage.py cleanup_tokens >> "$LogsDir\cleanup_tokens.log" 2>&1
"@ | Out-File -FilePath $CleanupBat -Encoding ASCII

# Bat-файл для удаления
@"
@echo off
cd /d "$ProjectDir"
"$PythonPath" manage.py cleanup_tokens --delete --days=90 >> "$LogsDir\cleanup_tokens.log" 2>&1
"@ | Out-File -FilePath $CleanupDeleteBat -Encoding ASCII

Write-Host "✅ Bat-файлы созданы:" -ForegroundColor Green
Write-Host "   - $CleanupBat"
Write-Host "   - $CleanupDeleteBat"
Write-Host ""

# Проверяем права администратора
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "⚠️  Внимание: Скрипт запущен без прав администратора" -ForegroundColor Yellow
    Write-Host "Для создания задач в Task Scheduler нужны права администратора" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Запустите PowerShell от имени администратора и повторите" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Или создайте задачи вручную через Task Scheduler:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Откройте Task Scheduler (taskschd.msc)" -ForegroundColor Cyan
    Write-Host "2. Создайте новую задачу:" -ForegroundColor Cyan
    Write-Host "   - Имя: Ghostwriter Cleanup Tokens" -ForegroundColor Cyan
    Write-Host "   - Триггер: Ежедневно в 02:00" -ForegroundColor Cyan
    Write-Host "   - Действие: $CleanupBat" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "3. Создайте вторую задачу:" -ForegroundColor Cyan
    Write-Host "   - Имя: Ghostwriter Delete Old Tokens" -ForegroundColor Cyan
    Write-Host "   - Триггер: Еженедельно (воскресенье) в 03:00" -ForegroundColor Cyan
    Write-Host "   - Действие: $CleanupDeleteBat" -ForegroundColor Cyan
    Write-Host ""
    exit 0
}

Write-Host "✅ Права администратора обнаружены" -ForegroundColor Green
Write-Host ""

# Создаем задачу 1: Деактивация истекших токенов
Write-Host "Создание задачи 1: Деактивация истекших токенов..." -ForegroundColor Cyan

$TaskName1 = "Ghostwriter Cleanup Tokens"

# Удаляем старую задачу если существует
if (Get-ScheduledTask -TaskName $TaskName1 -ErrorAction SilentlyContinue) {
    Write-Host "⚠️  Задача '$TaskName1' уже существует. Удаляем..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName1 -Confirm:$false
}

# Создаем действие
$Action1 = New-ScheduledTaskAction -Execute $CleanupBat

# Создаем триггер (каждый день в 2:00)
$Trigger1 = New-ScheduledTaskTrigger -Daily -At 2:00AM

# Создаем настройки
$Settings1 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Регистрируем задачу
Register-ScheduledTask -TaskName $TaskName1 -Action $Action1 -Trigger $Trigger1 -Settings $Settings1 -Description "Автоматическая деактивация истекших токенов Ghostwriter" -RunLevel Highest | Out-Null

Write-Host "✅ Задача '$TaskName1' создана" -ForegroundColor Green
Write-Host ""

# Создаем задачу 2: Удаление старых токенов
Write-Host "Создание задачи 2: Удаление старых токенов..." -ForegroundColor Cyan

$TaskName2 = "Ghostwriter Delete Old Tokens"

# Удаляем старую задачу если существует
if (Get-ScheduledTask -TaskName $TaskName2 -ErrorAction SilentlyContinue) {
    Write-Host "⚠️  Задача '$TaskName2' уже существует. Удаляем..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName2 -Confirm:$false
}

# Создаем действие
$Action2 = New-ScheduledTaskAction -Execute $CleanupDeleteBat

# Создаем триггер (каждое воскресенье в 3:00)
$Trigger2 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3:00AM

# Создаем настройки
$Settings2 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Регистрируем задачу
Register-ScheduledTask -TaskName $TaskName2 -Action $Action2 -Trigger $Trigger2 -Settings $Settings2 -Description "Автоматическое удаление старых деактивированных токенов Ghostwriter (>90 дней)" -RunLevel Highest | Out-Null

Write-Host "✅ Задача '$TaskName2' создана" -ForegroundColor Green
Write-Host ""

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "✅ Настройка завершена успешно!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Созданные задачи:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. $TaskName1" -ForegroundColor Green
Write-Host "   Расписание: Ежедневно в 02:00" -ForegroundColor Gray
Write-Host "   Команда: Деактивация истекших токенов" -ForegroundColor Gray
Write-Host ""
Write-Host "2. $TaskName2" -ForegroundColor Green
Write-Host "   Расписание: Еженедельно (воскресенье) в 03:00" -ForegroundColor Gray
Write-Host "   Команда: Удаление старых токенов (>90 дней)" -ForegroundColor Gray
Write-Host ""
Write-Host "Логи: $LogsDir\cleanup_tokens.log" -ForegroundColor Cyan
Write-Host ""
Write-Host "Для проверки задач:" -ForegroundColor Yellow
Write-Host "  Task Scheduler (taskschd.msc)" -ForegroundColor Gray
Write-Host ""
Write-Host "Для просмотра логов:" -ForegroundColor Yellow
Write-Host "  Get-Content '$LogsDir\cleanup_tokens.log' -Tail 50" -ForegroundColor Gray
Write-Host ""
Write-Host "Для ручного запуска:" -ForegroundColor Yellow
Write-Host "  py manage.py cleanup_tokens" -ForegroundColor Gray
Write-Host "  py manage.py cleanup_tokens --dry-run" -ForegroundColor Gray
Write-Host ""
Write-Host "Для запуска задачи сейчас:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName '$TaskName1'" -ForegroundColor Gray
Write-Host ""
