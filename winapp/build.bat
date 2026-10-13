@echo off
REM Build the md2pdf Windows GUI app (standalone, one-folder).
REM Run from anywhere; it operates on the md2pdf\ folder (parent of this script):
REM     winapp\build.bat
REM Optionally pass a specific Python:
REM     winapp\build.bat "C:\path\to\python.exe"
REM Output: dist\md2pdf\md2pdf.exe   (share by zipping the whole dist\md2pdf\ folder)
setlocal EnableDelayedExpansion

pushd "%~dp0.." || goto :err

REM --- find a WORKING Python with venv (skips broken ones like rtools) --------
set "PYEXE="

if not "%~1"=="" call :try "%~1"
if defined PYEXE goto :found
if defined PYTHON call :try "%PYTHON%"
if defined PYEXE goto :found

for %%V in (3.12 3.13 3.14 3.11 3) do (
    call :try "py -%%V"
    if defined PYEXE goto :found
)

call :try "python"
if defined PYEXE goto :found

for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "C:\Python314\python.exe"
    "C:\Python312\python.exe"
) do (
    call :try "%%~P"
    if defined PYEXE goto :found
)

echo.
echo Could not find a working Python with venv support.
echo Install Python 3.11+ from https://www.python.org/downloads/  (tick "Add to PATH"),
echo or re-run and name your Python explicitly, e.g.:
echo     winapp\build.bat "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
goto :err

:found
echo Using Python: !PYEXE!

echo [1/4] Creating build virtual environment...
!PYEXE! -m venv .venv-build || goto :err
call .venv-build\Scripts\activate.bat || goto :err

echo [2/4] Installing dependencies...
python -m pip install --upgrade pip || goto :err
python -m pip install markdown pygments websocket-client pyinstaller || goto :err

echo [3/4] Running PyInstaller...
python -m PyInstaller --noconfirm winapp\md2pdf.spec || goto :err

echo [4/4] Done.
echo.
echo Built: dist\md2pdf\md2pdf.exe
echo Share: zip the folder  dist\md2pdf\  and send it; recipients just run md2pdf.exe
popd
endlocal
goto :eof

REM --- :try "<python command>"  -> sets PYEXE if it runs and has venv ----------
:try
set "_C=%~1"
%_C% -c "import venv, ensurepip, sys; sys.exit(0)" >nul 2>&1
if errorlevel 1 goto :eof
set "PYEXE=%_C%"
goto :eof

:err
echo.
echo BUILD FAILED
popd 2>nul
endlocal
exit /b 1
