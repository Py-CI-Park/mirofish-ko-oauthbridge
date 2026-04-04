@echo off
setlocal

if not defined FRONTEND_PORT set "FRONTEND_PORT=3000"
if not defined BACKEND_PORT set "BACKEND_PORT=5001"
if not defined BRIDGE_PORT set "BRIDGE_PORT=8787"

set "FLASK_PORT=%BACKEND_PORT%"
set "PORT=%BRIDGE_PORT%"

echo [stop.bat] Stopping listeners on ports %FRONTEND_PORT%, %FLASK_PORT%, %PORT%...

powershell -NoProfile -ExecutionPolicy Bypass ^
  "$ports = @(%FRONTEND_PORT%, %FLASK_PORT%, %PORT%);" ^
  "$pids = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort } | Select-Object -ExpandProperty OwningProcess -Unique;" ^
  "if (-not $pids) { Write-Host '[stop.bat] No matching listening processes found.'; exit 0 }" ^
  "foreach ($pidValue in $pids) { try { Stop-Process -Id $pidValue -Force -ErrorAction Stop; Write-Host ('[stop.bat] Stopped PID ' + $pidValue) } catch { Write-Host ('[stop.bat] Failed to stop PID ' + $pidValue + ': ' + $_.Exception.Message) } }"

exit /b 0
