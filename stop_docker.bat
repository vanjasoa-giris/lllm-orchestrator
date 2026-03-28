@echo off
REM =====================================================
REM Script d'arret LLM Load Balancer Docker
REM =====================================================

echo Arret des services Docker...
docker-compose down

echo.
echo Services arretes.
pause
