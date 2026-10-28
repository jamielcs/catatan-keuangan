@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  Catatan APRILcell
echo  Membuka http://127.0.0.1:5000
echo  Tekan Ctrl+C untuk menghentikan server.
echo ============================================
if exist ".venv\Scripts\python.exe" goto runapp
echo ERROR: Virtual environment belum ada.
echo Jalankan install.bat terlebih dahulu.
pause
exit /b 1
:runapp
start "" /min cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:5000"
call ".venv\Scripts\python.exe" app.py
if errorlevel 1 goto gagal
exit /b 0
:gagal
echo.
echo ERROR: Aplikasi berhenti dengan kesalahan. Periksa pesan di atas.
pause
exit /b 1
