@echo off
rem Windows launcher. First run creates a private Python environment (.venv)
rem and installs the packages; later runs just start the app.
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
if not exist .venv (
  echo First run: setting things up ^(needs internet once^)...
  %PY% -m venv .venv || (echo Python 3.10+ is needed. Get it from python.org & pause & exit /b 1)
  .venv\Scripts\python -m pip install --upgrade pip -q
  .venv\Scripts\pip install -r requirements.txt -q
)
start "" .venv\Scripts\pythonw main.py %*
