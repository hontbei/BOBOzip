@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ================================
echo        UnzipTool 启动器
echo ================================
echo.

set "PY_CMD="

where py >nul 2>nul
if not errorlevel 1 (
    set "PY_CMD=py -3"
)

if not defined PY_CMD (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PY_CMD=python"
    )
)

if not defined PY_CMD (
    echo [错误] 没找到 Python。
    echo 请先安装 Python，并勾选 Add Python to PATH。
    echo.
    pause
    exit /b 1
)

echo [信息] 使用解释器: %PY_CMD%
echo [信息] 检查依赖...
%PY_CMD% -c "import customtkinter, rarfile, py7zr" >nul 2>nul
if errorlevel 1 (
    echo [信息] 缺少依赖，开始自动安装 requirements.txt ...
    %PY_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [错误] 依赖安装失败，请检查网络或 pip 配置。
        pause
        exit /b 1
    )
)

echo [信息] 正在启动图形界面...
%PY_CMD% unzip_gui.py

if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出。
    pause
)

endlocal
