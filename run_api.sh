#!/bin/bash
cd /root/hltv
PYTHONUNBUFFERED=1 uvicorn api.main:app --host 0.0.0.0 --port 5080 --reload
