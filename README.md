#анонимный мессенджер

##Сборка

###Создание окружения
```
python -m venv venv
```
###Активация окружения
```
/venv/Scripts/Activate.ps1
```
###Установка зависимостей
```
pip install requirements
```
###Компиляция в exe
```
pyinstaller --onefile --hidden-import=stem --hidden-import=flask --hidden-import=colorama --hidden-import=requests --hidden-import=pysocks --hidden-import=urllib3.contrib.socks --hidden-import=requests.packages.urllib3.contrib.socks --version-file=version_info.txt --add-data "app.manifest;." --icon=icon.ico m3tr0chat.py
```
###Цифровая подпись
```
signtool sign `
    /f "полный путь\my_cert.pfx" `
    /p "пароль" `
    /fd sha256 `
    /tr http://timestamp.digicert.com `
    /td sha256 `
    /d "M3tr0Chat" `
    /du "https://messenger.dm3tr0.ru" `
    /v "полный путь\m3tr0chat.exe"
```