@echo off
echo Starting LLM Workers...
start "Worker M1" cmd /k "python worker\main.py --port 8001 --id M1"
start "Worker M2" cmd /k "python worker\main.py --port 8002 --id M2"
start "Worker M3" cmd /k "python worker\main.py --port 8003 --id M3"
echo Workers started!
echo.
echo Now run: python orchestrator\main.py
pause
