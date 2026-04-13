@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

if not defined BRIDGE_PROVIDER set "BRIDGE_PROVIDER=codex"
if not defined CODEX_MODEL set "CODEX_MODEL=gpt-5.4-mini"
if not defined GEMINI_MODEL set "GEMINI_MODEL=gemini-2.5-flash"
if not defined CODEX_BRIDGE_WORKDIR set "CODEX_BRIDGE_WORKDIR=%CD%"

if not defined FRONTEND_PORT call :choose_port 3000 FRONTEND_PORT
if not defined BACKEND_PORT call :choose_port 5001 BACKEND_PORT
if not defined BRIDGE_PORT call :choose_port 8787 BRIDGE_PORT

set "FLASK_PORT=%BACKEND_PORT%"
set "PORT=%BRIDGE_PORT%"

if not defined FRONTEND_URL set "FRONTEND_URL=http://127.0.0.1:%FRONTEND_PORT%"
if not defined BACKEND_URL set "BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%/health"
if not defined BRIDGE_URL set "BRIDGE_URL=http://127.0.0.1:%BRIDGE_PORT%/health"
if not defined VITE_API_BASE_URL set "VITE_API_BASE_URL=http://127.0.0.1:%BACKEND_PORT%"
if not defined LLM_BASE_URL set "LLM_BASE_URL=http://127.0.0.1:%BRIDGE_PORT%/v1"

echo [run.bat] ROOT=%CD%
echo [run.bat] FRONTEND_PORT=%FRONTEND_PORT%
echo [run.bat] BACKEND_PORT=%BACKEND_PORT%
echo [run.bat] BRIDGE_PORT=%BRIDGE_PORT%
echo [run.bat] BRIDGE_PROVIDER=%BRIDGE_PROVIDER%
echo [run.bat] CODEX_MODEL=%CODEX_MODEL%
echo [run.bat] GEMINI_MODEL=%GEMINI_MODEL%
echo [run.bat] CODEX_BRIDGE_WORKDIR=%CODEX_BRIDGE_WORKDIR%
echo [run.bat] FRONTEND_URL=%FRONTEND_URL%
echo [run.bat] BACKEND_URL=%BACKEND_URL%
echo [run.bat] BRIDGE_URL=%BRIDGE_URL%
echo [run.bat] VITE_API_BASE_URL=%VITE_API_BASE_URL%
echo [run.bat] LLM_BASE_URL=%LLM_BASE_URL%

if not exist ".env" (
  echo [run.bat] WARNING: .env file not found in the project root.
  echo [run.bat] Copy .env.example to .env and fill in ZEP_API_KEY first.
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [run.bat] ERROR: npm was not found in PATH.
  exit /b 1
)

where uv >nul 2>nul
if errorlevel 1 (
  echo [run.bat] ERROR: uv was not found in PATH.
  exit /b 1
)

echo [run.bat] Launching bridge, backend, and frontend in separate windows...
start "MiroFish Bridge" /D "%CD%\codex-bridge" cmd /k ^
  set PORT=%BRIDGE_PORT%^&^& ^
  set BRIDGE_PROVIDER=%BRIDGE_PROVIDER%^&^& ^
  set CODEX_MODEL=%CODEX_MODEL%^&^& ^
  set GEMINI_MODEL=%GEMINI_MODEL%^&^& ^
  set CODEX_BRIDGE_WORKDIR=%CODEX_BRIDGE_WORKDIR%^&^& ^
  npm start

start "MiroFish Backend" /D "%CD%\backend" cmd /k ^
  set FLASK_PORT=%BACKEND_PORT%^&^& ^
  set LLM_BASE_URL=%LLM_BASE_URL%^&^& ^
  uv run python run.py

start "MiroFish Frontend" /D "%CD%\frontend" cmd /k ^
  set FRONTEND_PORT=%FRONTEND_PORT%^&^& ^
  set BACKEND_PORT=%BACKEND_PORT%^&^& ^
  set VITE_API_BASE_URL=%VITE_API_BASE_URL%^&^& ^
  npm run dev

echo [run.bat] Waiting for services to come up...
timeout /t 5 /nobreak >nul
node scripts\health-check.mjs --wait

if errorlevel 1 (
  echo [run.bat] One or more services did not become healthy in time.
  echo [run.bat] Check the opened command windows for errors.
  exit /b 1
)

echo [run.bat] All services look reachable.
echo [run.bat] Frontend: http://localhost:%FRONTEND_PORT%
echo [run.bat] Backend : http://localhost:%BACKEND_PORT%
echo [run.bat] Bridge  : http://127.0.0.1:%BRIDGE_PORT%/
exit /b 0

:choose_port
set "candidate=%~1"
set "targetVar=%~2"

:choose_port_loop
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "if (Get-NetTCPConnection -State Listen -LocalPort %candidate% -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }" >nul 2>nul
if errorlevel 1 (
  set /a candidate+=1
  goto :choose_port_loop
)

set "%targetVar%=%candidate%"
exit /b 0
