@echo off
REM Run a PR test build without touching production %%APPDATA%%\Integral.
setlocal EnableExtensions
set "ROOT=%~dp0"
set "INTEGRAL_DATA_DIR=%TEMP%\Integral-RunTest"
if not exist "%INTEGRAL_DATA_DIR%\" mkdir "%INTEGRAL_DATA_DIR%"
echo Isolated data folder (INTEGRAL_DATA_DIR):
echo   %INTEGRAL_DATA_DIR%
echo.
echo Window title should show TEST BUILD when using the bundled CI exe alone;
echo Run-Test.cmd forces this temp folder as a belt-and-braces override.
echo.
"%ROOT%Integral.exe"
endlocal
