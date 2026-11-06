@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  python -m venv .venv
  if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-llamacpp.ps1"
if errorlevel 1 goto failed
cd /d "%~dp0web"
call npm ci
if errorlevel 1 goto failed
node prepare.mjs
if errorlevel 1 goto failed
call npm run build
if errorlevel 1 goto failed
echo LocalDoc RAG WebNN est pret. Lancez demarrer-webnn.bat.
pause
exit /b 0
:failed
echo Installation interrompue. Consultez l'erreur ci-dessus.
pause
exit /b 1
