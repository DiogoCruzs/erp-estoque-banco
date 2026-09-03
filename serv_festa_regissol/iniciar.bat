@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao foi encontrado. Instale Python 3.11 ou superior e tente novamente.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente local...
  python -m venv .venv
)
echo Verificando dependencias...
.venv\Scripts\python.exe -m pip install -r requirements.txt
start "SERV FESTA REGISSOL" http://127.0.0.1:5000
echo Sistema iniciado em http://127.0.0.1:5000
.venv\Scripts\python.exe run.py
pause

