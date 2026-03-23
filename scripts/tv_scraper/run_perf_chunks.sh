#!/bin/bash
# Run perf scraper in chunks of 5, fresh browser each time
# Resume-safe: skips already-scraped strategies

PYTHON="/Users/nyra/Projects/pyhood/.venv/bin/python"
SCRIPT="/Users/nyra/Projects/pyhood/scripts/tv_scraper/tv_perf_scrape.py"
LOG="/Users/nyra/Projects/pyhood/scripts/tv_scraper/data/perf_scrape_chunks.log"
CHUNK=5
TOTAL=1000

echo "$(date) Starting chunked perf scrape (chunk=$CHUNK)" | tee -a "$LOG"

for ((i=0; i<TOTAL; i+=CHUNK)); do
    # Count how many already scraped
    DONE=$($PYTHON -c "
import json
with open('/Users/nyra/Projects/pyhood/scripts/tv_scraper/data/strategies_classified.json') as f:
    data = json.load(f)
print(sum(1 for s in data if s.get('perf_scraped')))
" 2>/dev/null)
    
    if [ "$DONE" -ge "$TOTAL" ]; then
        echo "$(date) All $TOTAL strategies scraped!" | tee -a "$LOG"
        break
    fi
    
    echo "$(date) Chunk starting at $i (total scraped: $DONE/$TOTAL)" | tee -a "$LOG"
    
    $PYTHON "$SCRIPT" --limit $CHUNK --start-from $i >> "$LOG" 2>&1
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -ne 0 ]; then
        echo "$(date) Chunk at $i failed with exit $EXIT_CODE, continuing..." | tee -a "$LOG"
    fi
    
    # Brief pause between chunks
    sleep 2
done

echo "$(date) Chunked perf scrape complete" | tee -a "$LOG"
