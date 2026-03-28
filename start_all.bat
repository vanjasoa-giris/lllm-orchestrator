@echo off
echo Starting LLM Workers and Orchestrator...
start "Worker M1" cmd /k "python worker\main.py --port 8001 --id M1"
start "Worker M2" cmd /k "python worker\main.py --port 8002 --id M2"
start "Worker M3" cmd /k "python worker\main.py --port 8003 --id M3"
timeout /t 3 /nobreak > nul
start "Orchestrator" cmd /k "python orchestrator\main.py"
echo All services started!
echo.
echo - Worker M1: http://localhost:8001
echo - Worker M2: http://localhost:8002
echo - Worker M3: http://localhost:8003
echo - Orchestrator: http://localhost:8000
pause
