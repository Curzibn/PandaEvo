@echo off
chcp 65001 >nul
title PandaEvo

echo Starting python-service on port 10600...
start "python-service" cmd /k "cd /d %~dp0python-service && uv run uvicorn main:app --reload --port 10600"

timeout /t 2 >nul

echo Starting web-pc on port 10601...
start "web-pc" cmd /k "cd /d %~dp0web-pc && npm run dev -- --port 10601"
