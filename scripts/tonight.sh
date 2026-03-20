#!/bin/bash
# Tonight's autoresearch run — SPY 10yr
cd ~/Projects/pyhood

echo "=== AUTORESEARCH OVERNIGHT RUN ==="
echo "Started: $(date)"
echo "Ticker: SPY, Period: 10y, Slippage: 0.01%"
echo ""

# Run with nohup so it survives terminal close
.venv/bin/python scripts/run_overnight.py \
  --ticker SPY \
  --period 10y \
  --results-dir autoresearch_results/spy_$(date +%Y%m%d) \
  --slippage 0.01 \
  --timeout 60 \
  2>&1 | tee autoresearch_results/spy_$(date +%Y%m%d)_console.log

echo ""
echo "=== COMPLETED: $(date) ==="
