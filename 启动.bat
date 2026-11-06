@echo off
chcp 65001 >nul
title 医院智能导诊 AI 客服
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
echo.
echo 服务已停止，按任意键关闭窗口。
pause >nul
