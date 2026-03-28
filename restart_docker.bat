@echo off
REM =====================================================
REM Script de redemarrage LLM Load Balancer Docker
REM =====================================================

echo Arret des services...
docker-compose down

echo.
echo Construction et demarrage...
docker-compose build
docker-compose up -d

echo.
echo Redemarrage termine.
pause
