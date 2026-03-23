#!/bin/bash
cd "$(dirname "$0")/.."
.venv/bin/streamlit run dashboard/app.py --server.port 8501
