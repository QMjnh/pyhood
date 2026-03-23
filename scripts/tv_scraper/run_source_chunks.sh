#!/bin/bash
# Run source scraper in chunks of 5, fresh browser each time
# Resume-safe: skips already-scraped strategies

PYTHON="/Users/nyra/Projects/pyhood/.venv/bin/python"
SCRIPT="/Users/nyra/Projects/pyhood/scripts/tv_scraper/tv_source_scrape.py"
INPUT="/Users/nyra/Projects/pyhood/scripts/tv_scraper/data/candidates_71.json"
LOG="/Users/nyra/Projects/pyhood/scripts/tv_scraper/data/source_scrape_chunks.log"
CHUNK=5

# Get total count from input file
TOTAL=$($PYTHON -c "import json; print(len(json.load(open('$INPUT'))))" 2>/dev/null)
if [ -z "$TOTAL" ] || [ "$TOTAL" -eq 0 ]; then
    echo "$(date) ERROR: Could not read input file or empty" | tee -a "$LOG"
    exit 1
fi

echo "$(date) Starting chunked source scrape (chunk=$CHUNK, total=$TOTAL)" | tee -a "$LOG"

for ((i=0; i<TOTAL; i+=CHUNK)); do
    # Count how many .pine files exist
    DONE=$(find "/Users/nyra/Projects/pyhood/scripts/tv_scraper/data/pine_scripts" -name "*.pine" -size +0c 2>/dev/null | wc -l | tr -d ' ')

    echo "$(date) Chunk starting at $i (pine files: $DONE/$TOTAL)" | tee -a "$LOG"

    $PYTHON "$SCRIPT" --input "$INPUT" --limit $CHUNK --start-from $i >> "$LOG" 2>&1
    EXIT_CODE=$?

    if [ $EXIT_CODE -ne 0 ]; then
        echo "$(date) Chunk at $i failed with exit $EXIT_CODE, continuing..." | tee -a "$LOG"
    fi

    # Brief pause between chunks
    sleep 2
done

echo "$(date) Chunked source scrape complete ($(find '/Users/nyra/Projects/pyhood/scripts/tv_scraper/data/pine_scripts' -name '*.pine' -size +0c 2>/dev/null | wc -l | tr -d ' ') pine files)" | tee -a "$LOG"
