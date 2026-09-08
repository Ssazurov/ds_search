@echo off
REM Запуск Streamlit-приложения ds_search (WSL) для закачки/поиска материалов
wsl.exe bash -lc "cd /home/vector/projects/ds/ds_search && .venv/bin/python3 -m streamlit run ui/app.py"
pause
