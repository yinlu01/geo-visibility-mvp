#!/usr/bin/env bash
# GEO MVP 启动脚本
set -e
cd "$(dirname "$0")"

PY=${PYTHON:-python3}

if [ ! -d .venv ]; then
  echo "==> 创建虚拟环境"
  "$PY" -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt

echo "==> 启动 http://localhost:8501"
streamlit run app.py --server.port 8501 --server.headless true
