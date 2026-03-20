@echo off
cd /d %~dp0..
call .venv\Scripts\activate
python monitor_alertas.py
