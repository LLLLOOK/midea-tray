@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === 1/2 创建虚拟环境 ===
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo 创建失败, 请确认已安装 Python 3.10+ 并加入 PATH
        pause
        exit /b 1
    )
)

echo === 2/2 安装依赖 ===
".venv\Scripts\python.exe" -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
".venv\Scripts\python.exe" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo 依赖安装失败
    pause
    exit /b 1
)

echo.
echo 安装完成。
echo 接下来运行 setup.bat 获取设备 token（只需一次）。
pause
