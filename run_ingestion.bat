@echo off
REM Запуск ds_ingestion (FastAPI, порт 8200) для /reload_by_gar_id
wsl.exe bash -lc "cd /home/vector/projects/ds/ds_ingestion && .venv/bin/python3 -m uvicorn src.adapter.api:app --host 127.0.0.1 --port 8200"
pause
