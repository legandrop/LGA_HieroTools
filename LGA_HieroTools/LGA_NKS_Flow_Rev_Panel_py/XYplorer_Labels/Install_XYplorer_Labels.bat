@echo off
rem Instala los labels de XYplorer que usa Flow Pull (ver Install_XYplorer_Labels.ps1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install_XYplorer_Labels.ps1" %*
pause
