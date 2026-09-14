#!/bin/bash
set -e
cd /Users/yinlu01/WorkBuddy/2026-09-11-13-44-35/geo-mvp
exec /Users/yinlu01/.workbuddy/binaries/python/envs/default/bin/streamlit run app.py \
  --server.port 8501 --server.headless true --server.address 127.0.0.1
