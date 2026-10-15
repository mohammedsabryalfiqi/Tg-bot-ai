@echo off
REM SmarTel - one-command start (Windows)
REM
REM   start.bat
REM
REM Creates a virtual environment if needed, installs the dependencies, then
REM runs the bot. The owner claim code is printed here on the first run - send
REM "/start <code>" to your bot in Telegram.
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10+ is required but "python" was not found in PATH.
  pause
  exit /b 1
)

if not exist ".venv" (
  echo ==^> Creating the virtual environment (.venv)
  python -m venv .venv
)
call .venv\Scripts\activate.bat

if not exist ".venv\.deps-installed" (
  echo ==^> Installing dependencies
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt
  echo done> .venv\.deps-installed
)

if not exist ".env" (
  echo ==^> No .env found: the first-run wizard will ask for your bot token.
)

python main.py %*
endlocal
