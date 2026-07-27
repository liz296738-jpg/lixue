@echo off
REM ============================================================
REM  Report Automator Pro — One-Click Build Script
REM ============================================================
REM  Compiles gui_main.py into a standalone Windows .exe
REM  with all dependencies bundled.
REM
REM  Requirements:
REM    - Python 3.11+ with pip
REM    - PyInstaller >= 6.0
REM
REM  Output: dist/ReportAutomatorPro.exe
REM ============================================================

echo.
echo ============================================================
echo   Report Automator Pro — Build Script
echo ============================================================
echo.

REM --- Ensure dependencies are installed ---
echo [1/3] Checking dependencies ...
pip install -r requirements.txt --quiet
pip install customtkinter pyinstaller --quiet
echo       Done.

REM --- Clean previous build ---
echo [2/3] Cleaning previous build artifacts ...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist "*.spec" del /q "*.spec"
echo       Done.

REM --- PyInstaller build ---
echo [3/3] Compiling standalone executable ...
echo       This may take 2-5 minutes ...

pyinstaller ^
    --name="ReportAutomatorPro" ^
    --windowed ^
    --onefile ^
    --clean ^
    --add-data="src;src" ^
    --add-data="output;output" ^
    --add-data="templates;templates" ^
    --add-data="requirements.txt;." ^
    --hidden-import=customtkinter ^
    --hidden-import=pyvista ^
    --hidden-import=vtk ^
    --hidden-import=vtkmodules.all ^
    --hidden-import=matplotlib ^
    --hidden-import=pptx ^
    --hidden-import=numpy ^
    --hidden-import=PIL ^
    --hidden-import=darkdetect ^
    --collect-all=numpy ^
    --collect-all=pyvista ^
    --collect-all=vtk ^
    --exclude-module=tkinter.test ^
    --noconfirm ^
    gui_main.py

echo.
echo ============================================================
echo   Build complete!
echo   Executable: dist\ReportAutomatorPro.exe
echo ============================================================
echo.
pause
