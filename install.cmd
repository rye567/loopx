@echo off
setlocal
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%~dp0install.py" %*
) else (
  python "%~dp0install.py" %*
)
