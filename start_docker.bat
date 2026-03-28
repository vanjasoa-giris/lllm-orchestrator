@echo off
REM =====================================================
REM Script de demarrage LLM Load Balancer avec Docker
REM =====================================================

echo =====================================================
echo    LLM Load Balancer - Docker Startup
echo =====================================================

REM Verifier que Docker est en cours d'execution
docker version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker n'est pas en cours d'execution.
    echo Demarrez Docker Desktop et réessayez.
    pause
    exit /b 1
)

echo.
echo [1/3] Construction des images Docker...
docker-compose build

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Echec de la construction des images.
    pause
    exit /b 1
)

echo.
echo [2/3] Demarrage des services...
docker-compose up -d

echo.
echo [3/3] Verification des services...
timeout /t 5 /nobreak >nul

echo.
echo =====================================================
echo    STATUT DU SYSTEME
echo =====================================================
echo.
docker-compose ps
echo.
echo --- URLs ---
echo Orchestrateur: http://localhost:8000
echo Dashboard:     http://localhost:8000/
echo Stats:         http://localhost:8000/stats
echo Metrics:       http://localhost:8000/metrics
echo Health:        http://localhost:8000/health
echo.
echo --- Workers ---
echo Worker M1: http://localhost:8001
echo Worker M2: http://localhost:8002
echo Worker M3: http://localhost:8003
echo.
echo --- Logs ---
echo docker-compose logs -f
echo.
echo --- Arreter ---
echo docker-compose down
echo =====================================================

REM Ouvrir le dashboard dans le navigateur
start http://localhost:8000/
