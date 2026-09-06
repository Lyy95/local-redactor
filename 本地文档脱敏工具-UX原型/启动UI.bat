@echo off
setlocal
cd /d "%~dp0"

set "APP_URL=http://127.0.0.1:5173/"
set "APP_DIR=%CD%"
set "NODE_EXE="

curl.exe --silent --fail --max-time 2 "%APP_URL%" >nul 2>nul
if not errorlevel 1 goto open_ui

for /f "delims=" %%I in ('where node.exe 2^>nul') do if not defined NODE_EXE set "NODE_EXE=%%I"
if not defined NODE_EXE if exist "D:\Program Files\nodejs\node.exe" set "NODE_EXE=D:\Program Files\nodejs\node.exe"
if not defined NODE_EXE if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" set "NODE_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"

if not defined NODE_EXE (
  echo Node.js was not found. Please install Node.js, then try again.
  pause
  exit /b 1
)

if not exist "node_modules\vite\bin\vite.js" (
  echo Project dependencies are missing. Please run npm install first.
  pause
  exit /b 1
)

powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath $env:NODE_EXE -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173') -WorkingDirectory $env:APP_DIR -WindowStyle Hidden"

for /l %%N in (1,1,20) do (
  curl.exe --silent --fail --max-time 2 "%APP_URL%" >nul 2>nul
  if not errorlevel 1 goto open_ui
  timeout /t 1 /nobreak >nul
)

echo The UI did not start. Please check the minimized server window.
pause
exit /b 1

:open_ui
powershell.exe -NoProfile -Command "Start-Process $env:APP_URL"
endlocal
