@echo off
echo Iniciando Sistema de Repertorio...
echo.

REM Comprobar si Flask esta instalado
python -c "import flask" 2>nul
if %errorlevel% neq 0 (
    echo Instalando dependencias de Flask y CORS...
    pip install flask flask-cors
) else (
    echo Dependencias listas.
)

echo.
echo ==============================================================
echo Servidor Iniciado.
echo Puedes abrir tu navegador en: http://localhost:5000
echo Si estas en otra PC o celular, entra a: http://TU_IP_LOCAL:5000
echo ==============================================================
echo.

python app.py
pause
