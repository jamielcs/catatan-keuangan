@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  Catatan APRILcell - Instalasi
echo ============================================
where python >nul 2>nul
if errorlevel 1 goto nopython
python --version
if not exist ".venv" goto createvenv
echo Virtual environment sudah ada, lewati pembuatan.
goto installdeps
:createvenv
echo Membuat virtual environment...
python -m venv .venv
if errorlevel 1 goto gagal
:installdeps
echo Memasang dependensi dari requirements.txt ...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto gagal
if not exist "instance" mkdir instance
if not exist "backups" mkdir backups
echo Menyiapkan database tanpa menghapus data yang sudah ada...
call ".venv\Scripts\python.exe" -c "from app import create_app; create_app(); print('Database siap.')"
if errorlevel 1 goto gagal
echo.
echo Instalasi selesai. Jalankan run.bat untuk membuka aplikasi.
pause
exit /b 0
:nopython
echo ERROR: Python tidak ditemukan di komputer ini.
echo Silakan install Python 3.11 atau lebih baru dari python.org lalu centang Add python.exe to PATH.
pause
exit /b 1
:gagal
echo.
echo ERROR: Instalasi gagal. Periksa pesan di atas dan koneksi internet saat pemasangan dependensi.
pause
exit /b 1
