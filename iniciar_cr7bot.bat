@echo off
REM === CR7 BOT - Análise de Apostas ===
cd /d "%~dp0"
echo A iniciar o CR7 BOT...
start "" streamlit run cr7bot_streamlit.py
echo.
echo Fecha esta janela apenas quando terminares.
pause
