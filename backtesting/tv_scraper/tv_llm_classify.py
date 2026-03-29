#!/usr/bin/env python3
"""
LLM-powered strategy classifier for TradingView strategies.

Reads strategies_enriched.json (or strategies_classified.json if regex pass was done first),
sends batches of descriptions to Claude Sonnet for semantic classification,
and outputs strategies_classified.json with rich metadata.

Usage:
    ~/Projects/pyhood/.venv/bin/python tv_llm_classify.py
    ~/Projects/pyhood/.venv/bin/python tv_llm_classify.py --limit 20 --batch-size 10
    ~/Projects/pyhood/.venv/bin/python tv_llm_classify.py --input data/strategies_enriched.json
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import anthropic

# Paths
DATA_DIR = Path(__file__).parent / "data"
DEFAULT_INPUT = DATA_DIR / "strategies_enriched.json"
DEFAULT_OUTPUT = DATA_DIR / "strategies_classified.json"
LOG_FILE = DATA_DIR / "classify_llm.log"

# LLM settings
MODEL = "claude-sonnet-4-20250514"
BATCH_SIZE = 15  # strategies per API call
RATE_LIMIT_DELAY = 1.0  # seconds between API calls

CLASSIFICATION_PROMPT = """You are a trading strategy classifier. For each strategy below, analyze the title, description, and tags to extract structured metadata.

Return a JSON array with one object per strategy (in the same order as input). Each object must have these fields:

{
  "index": <integer, matches input index>,
  "ticker": <string or null — primary ticker/symbol this strategy is designed for. Examples: "BTCUSDT", "SPY", "ES", "XAUUSD", "EURUSD", "AAPL". Use the most specific form available. null if truly generic/unknown>,
  "timeframe": <string or null — normalized timeframe. Use: "15s", "1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W", "1M". null if not determinable>,
  "asset_class": <string — one of: "crypto", "equities", "futures", "forex", "commodities", "options", "multi", "unknown">,
  "trading_style": <string — one of: "scalp", "intraday", "swing", "position", "unknown">,
  "regime_tags": <array of strings — market conditions where this strategy works. Pick ALL that apply from: "trending", "ranging", "high_volatility", "low_volatility", "bullish", "bearish", "breakout", "momentum", "mean_reversion", "news_driven">,
  "strategy_category": <string — one of: "trend_following", "mean_reversion", "breakout", "momentum", "volatility", "statistical_arbitrage", "pattern_recognition", "multi_strategy", "other">,
  "indicators_used": <array of strings — key technical indicators. Examples: "EMA", "RSI", "MACD", "VWAP", "Bollinger Bands", "ATR", "Stochastic", "Ichimoku", "Volume Profile", "Supertrend">,
  "risk_profile": <string — one of: "conservative", "moderate", "aggressive">
}

Rules:
- If the description is empty or uninformative, do your best from title and tags alone
- For ticker: prefer what's explicitly mentioned. "ES" = E-mini S&P futures, "NQ" = Nasdaq futures, "GC" = Gold futures, "CL" = Crude Oil futures
- For regime_tags: infer from strategy type if not stated. Moving average crossovers → "trending". RSI/Bollinger → "mean_reversion" or "ranging". Breakout strategies → "breakout". High-frequency scalpers → "high_volatility"
- For trading_style: infer from timeframe if not stated. ≤15m → "scalp", 30m-4H → "intraday", 1D → "swing", 1W+ → "position"
- Be conservative with regime_tags — only tag what's clearly supported
- Return ONLY the JSON array, no other text

Here are the strategies to classify:

"""


def setup_logging() -> logging.Logger:
    """Setup logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def load_strategies(input_path: Path) -> list[dict]:
    """Load strategies from JSON file."""
    with open(input_path) as f:
        return json.load(f)


def load_existing_classifications(output_path: Path) -> dict:
    """Load existing classifications for resume support."""
    if output_path.exists():
        with open(output_path) as f:
            data = json.load(f)
        # Index by script_url for lookup
        return {s['script_url']: s for s in data}
    return {}


def format_strategy_for_prompt(index: int, strategy: dict) -> str:
    """Format a single strategy for the classification prompt."""
    title = strategy.get('title', 'Unknown')
    description = (strategy.get('description') or '')[:800]  # Cap description length
    tags = ', '.join(strategy.get('tags') or [])
    existing_ticker = strategy.get('default_ticker') or 'unknown'
    existing_timeframe = strategy.get('default_timeframe') or 'unknown'
    strategy_type = strategy.get('strategy_type') or 'unknown'

    return (
        f"[Strategy {index}]\n"
        f"Title: {title}\n"
        f"Current ticker: {existing_ticker}\n"
        f"Current timeframe: {existing_timeframe}\n"
        f"Strategy type: {strategy_type}\n"
        f"Tags: {tags}\n"
        f"Description: {description}\n"
    )


def classify_batch(client: anthropic.Anthropic, batch: list[tuple[int, dict]], 
                   logger: logging.Logger) -> list[dict]:
    """Send a batch of strategies to Claude for classification."""
    # Build prompt
    strategies_text = "\n---\n".join(
        format_strategy_for_prompt(idx, s) for idx, s in batch
    )
    prompt = CLASSIFICATION_PROMPT + strategies_text

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse response
        response_text = response.content[0].text.strip()
        
        # Handle potential markdown wrapping
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])
        
        classifications = json.loads(response_text)
        return classifications
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        logger.error(f"Response text: {response_text[:500]}")
        return []
    except anthropic.APIError as e:
        logger.error(f"API error: {e}")
        return []


def merge_classification(strategy: dict, classification: dict) -> dict:
    """Merge LLM classification into strategy data."""
    result = strategy.copy()
    
    # Fill ticker if currently missing
    if not result.get('default_ticker') and classification.get('ticker'):
        result['default_ticker'] = classification['ticker']
    
    # Fill timeframe if currently missing  
    if not result.get('default_timeframe') and classification.get('timeframe'):
        result['default_timeframe'] = classification['timeframe']
    
    # Add new classification fields
    result['asset_class'] = classification.get('asset_class', 'unknown')
    result['trading_style'] = classification.get('trading_style', 'unknown')
    result['regime_tags'] = classification.get('regime_tags', [])
    result['strategy_category'] = classification.get('strategy_category', 'other')
    result['indicators_used'] = classification.get('indicators_used', [])
    result['risk_profile'] = classification.get('risk_profile', 'moderate')
    result['llm_classified'] = True
    
    return result


def print_summary(strategies: list[dict], logger: logging.Logger):
    """Print classification summary statistics."""
    total = len(strategies)
    classified = sum(1 for s in strategies if s.get('llm_classified'))
    
    logger.info(f"\n{'='*60}")
    logger.info(f"CLASSIFICATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total strategies: {total}")
    logger.info(f"LLM classified: {classified}")
    logger.info(f"With tickers: {sum(1 for s in strategies if s.get('default_ticker'))}")
    logger.info(f"With timeframes: {sum(1 for s in strategies if s.get('default_timeframe'))}")
    
    # Asset class breakdown
    from collections import Counter
    asset_classes = Counter(s.get('asset_class', 'unknown') for s in strategies if s.get('llm_classified'))
    logger.info(f"\nAsset Classes:")
    for ac, count in asset_classes.most_common():
        logger.info(f"  {ac}: {count}")
    
    # Trading style breakdown
    styles = Counter(s.get('trading_style', 'unknown') for s in strategies if s.get('llm_classified'))
    logger.info(f"\nTrading Styles:")
    for style, count in styles.most_common():
        logger.info(f"  {style}: {count}")
    
    # Strategy category breakdown
    categories = Counter(s.get('strategy_category', 'other') for s in strategies if s.get('llm_classified'))
    logger.info(f"\nStrategy Categories:")
    for cat, count in categories.most_common():
        logger.info(f"  {cat}: {count}")
    
    # Regime tags breakdown
    regime_counts = Counter()
    for s in strategies:
        if s.get('llm_classified'):
            for tag in s.get('regime_tags', []):
                regime_counts[tag] += 1
    logger.info(f"\nRegime Tags:")
    for tag, count in regime_counts.most_common():
        logger.info(f"  {tag}: {count}")
    
    # Risk profile breakdown
    risks = Counter(s.get('risk_profile', 'unknown') for s in strategies if s.get('llm_classified'))
    logger.info(f"\nRisk Profiles:")
    for risk, count in risks.most_common():
        logger.info(f"  {risk}: {count}")

    logger.info(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="LLM-powered strategy classifier")
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT),
                       help="Input JSON file")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT),
                       help="Output JSON file")
    parser.add_argument("--limit", type=int, default=None,
                       help="Limit number of strategies to classify")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                       help=f"Strategies per API call (default: {BATCH_SIZE})")
    parser.add_argument("--delay", type=float, default=RATE_LIMIT_DELAY,
                       help=f"Seconds between API calls (default: {RATE_LIMIT_DELAY})")
    args = parser.parse_args()
    
    logger = setup_logging()
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    logger.info("Starting LLM strategy classification")
    logger.info(f"Input: {input_path}")
    logger.info(f"Output: {output_path}")
    logger.info(f"Batch size: {args.batch_size}, Delay: {args.delay}s")
    
    # Load strategies
    strategies = load_strategies(input_path)
    logger.info(f"Loaded {len(strategies)} strategies")
    
    # Load existing classifications for resume
    existing = load_existing_classifications(output_path)
    
    # Find strategies that need classification
    to_classify = []
    already_done = []
    for i, s in enumerate(strategies):
        url = s['script_url']
        if url in existing and existing[url].get('llm_classified'):
            already_done.append(existing[url])
        else:
            to_classify.append((i, s))
    
    logger.info(f"Already classified: {len(already_done)}")
    logger.info(f"Need classification: {len(to_classify)}")
    
    if args.limit:
        to_classify = to_classify[:args.limit]
        logger.info(f"Limited to: {len(to_classify)}")
    
    # Initialize Anthropic client
    client = anthropic.Anthropic()
    
    # Process in batches
    classified = list(already_done)
    # Track indices of already-classified URLs
    classified_urls = {s['script_url'] for s in already_done}
    
    total_batches = (len(to_classify) + args.batch_size - 1) // args.batch_size
    
    for batch_num in range(total_batches):
        start = batch_num * args.batch_size
        end = min(start + args.batch_size, len(to_classify))
        batch = to_classify[start:end]
        
        logger.info(f"Batch {batch_num + 1}/{total_batches}: "
                    f"classifying strategies {start + 1}-{end}")
        
        # Classify batch
        results = classify_batch(client, batch, logger)
        
        if results:
            # Merge results back
            for classification in results:
                idx = classification.get('index')
                # Find the matching strategy
                match = None
                for orig_idx, s in batch:
                    if orig_idx == idx:
                        match = s
                        break
                
                if match:
                    merged = merge_classification(match, classification)
                    classified.append(merged)
                    classified_urls.add(merged['script_url'])
                else:
                    logger.warning(f"No match for classification index {idx}")
        else:
            logger.warning(f"Batch {batch_num + 1} returned no results, "
                         f"keeping originals")
            for orig_idx, s in batch:
                if s['script_url'] not in classified_urls:
                    classified.append(s)
                    classified_urls.add(s['script_url'])
        
        # Save progress every 5 batches
        if (batch_num + 1) % 5 == 0:
            # Add any unclassified strategies
            all_output = list(classified)
            for i, s in enumerate(strategies):
                if s['script_url'] not in classified_urls:
                    all_output.append(s)
            with open(output_path, 'w') as f:
                json.dump(all_output, f, indent=2, ensure_ascii=False)
            logger.info(f"Progress saved: {len(classified)} classified")
        
        # Rate limit
        if batch_num < total_batches - 1:
            time.sleep(args.delay)
    
    # Add any remaining unclassified strategies
    for s in strategies:
        if s['script_url'] not in classified_urls:
            classified.append(s)
    
    # Save final output
    with open(output_path, 'w') as f:
        json.dump(classified, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n✅ Classification complete!")
    logger.info(f"💾 Saved to: {output_path}")
    
    # Print summary
    print_summary(classified, logger)


if __name__ == "__main__":
    main()
