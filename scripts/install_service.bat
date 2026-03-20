@echo off
REM Instala CCU-TRT Monitor como servicio de Windows usando NSSM
REM Requiere NSSM (https://nssm.cc/) y ejecutar como Administrador

SET APP_DIR=%~dp0..
SET PYTHON_EXE=python
SET SERVICE_NAME=CCU-TRT-Monitor

echo ============================================
echo  Instalador de Servicio CCU-TRT Monitor
echo ============================================

REM Verificar si se ejecuta como admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: Debes ejecutar este script como Administrador
    pause
    exit /b 1
)

REM Verificar si NSSM existe
where nssm >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: NSSM no encontrado. Descargalo de https://nssm.cc/
    pause
    exit /b 1
)

echo.
echo Instalando servicio...
nssm install %SERVICE_NAME% "%PYTHON_EXE%" "%APP_DIR%\web_app.py"
nssm set %SERVICE_NAME% AppDirectory "%APP_DIR%"
nssm set %SERVICE_NAME% DisplayName "CCU TRT Monitor Web"
nssm set %SERVICE_NAME% Description "Sistema de Alertas de Tiempo de Residencia en Planta"
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START
nssm set %SERVICE_NAME% AppStdout "%APP_DIR%\logs\service.log"
nssm set %SERVICE_NAME% AppStderr "%APP_DIR%\logs\service_error.log"

echo.
echo Servicio instalado. Iniciando...
nssm start %SERVICE_NAME%

echo.
echo ============================================
echo  Servicio instalado y corriendo
echo  Accede a: http://localhost:8080
echo ============================================
pause
