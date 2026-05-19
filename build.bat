@echo off
echo Starting build process...

:: Удаление старых папок, если они есть
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

:: Сборка приложения
:: --noconsole: скрыть черное окно (актуально, если в коде есть ctypes.windll...ShowWindow)
:: --onefile: собрать все в один EXE
:: --icon: путь к иконке
:: --add-data: добавление внешних файлов (формат "файл;папка_в_exe")
pyinstaller --noconsole --onefile ^
 --icon=icon.ico ^
 --add-data "settings.json;." ^
 --add-data "locales.json;." ^
 app.py

echo Build completed! Your file is in the 'dist' folder.
pause