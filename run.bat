@echo off
rem Windows launcher. First run creates a private Python environment (.venv)
rem and installs the packages; later runs just start the app.
rem
rem v1.1 fix: pehle sirf ".venv folder hai ya nahi" dekhte the. Install beech
rem mein fail ho toh folder reh jaata tha aur agli baar install skip hota tha.
rem Ab install poora hone par hi .venv\.likhit-ready marker banta hai. Koi step
rem fail ho toh marker nahi banta, toh agli baar setup dobara chalega.
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
if exist .venv\.likhit-ready goto run
echo Setting things up ^(needs internet once^)...
if not exist .venv\Scripts\python.exe (
  %PY% -m venv .venv || (echo Python 3.10+ is needed. Get it from python.org & pause & exit /b 1)
)
.venv\Scripts\python -m pip install --upgrade pip -q
.venv\Scripts\python -m pip install -r requirements.txt -q || (echo Setup failed. Check your internet and run again. & pause & exit /b 1)
echo ok> .venv\.likhit-ready
:run
start "" .venv\Scripts\pythonw main.py %*
