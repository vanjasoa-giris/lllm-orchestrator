@echo off
REM LLM Orchestrator Visualization - Quick Start (Windows)

echo.
echo ========================================
echo  LLM ORCHESTRATOR - VISUALIZATION DEMO
echo ========================================
echo.

REM Start full stack
echo Starting Docker Compose stack...
docker-compose -f docker-compose.v2.yml up -d

REM Wait for services
echo.
echo Waiting for services to start (10s)...
timeout /t 10 /nobreak

REM Show containers
echo.
echo Running containers:
docker-compose -f docker-compose.v2.yml ps

REM Show URLs
echo.
echo ========================================
echo  ACCESS DASHBOARDS:
echo ========================================
echo.
echo   WebUI (Real-time):     http://localhost:8000
echo   Grafana:               http://localhost:3000 (admin/admin)
echo   Prometheus:            http://localhost:9090
echo.

REM Show next steps
echo ========================================
echo  NEXT STEPS:
echo ========================================
echo.
echo   1. Open http://localhost:8000 in browser
echo   2. In new terminal, run: python demo_load.py
echo   3. Watch the dashboard update in real-time!
echo.
echo   OR: Run 'start.bat' to start demo automatically
echo.

pause
