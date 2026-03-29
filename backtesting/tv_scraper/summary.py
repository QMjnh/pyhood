#!/usr/bin/env python3
"""
Summary script for TradingView scraper data.
Shows overview of scraped and enriched strategies.
"""

import json
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime

def load_strategies():
    """Load original strategies."""
    strategies_file = Path(__file__).parent / "data" / "strategies.json"
    
    if not strategies_file.exists():
        return []
    
    with open(strategies_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_enriched_strategies():
    """Load enriched strategies."""
    enriched_file = Path(__file__).parent / "data" / "strategies_enriched.json"
    
    if not enriched_file.exists():
        return []
    
    with open(enriched_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    """Main function."""
    print("📊 TradingView Scraper Summary")
    print("=" * 50)
    
    # Load data
    strategies = load_strategies()
    enriched = load_enriched_strategies()
    
    print(f"\n📈 Original Strategies: {len(strategies)}")
    if strategies:
        boost_counts = [s.get('boost_count', 0) for s in strategies]
        print(f"   Total boost count: {sum(boost_counts):,}")
        print(f"   Average boosts: {sum(boost_counts) / len(strategies):.1f}")
        print(f"   Top strategy: {max(boost_counts)} boosts")
        
        # Top authors
        authors = [s.get('author', 'Unknown') for s in strategies]
        author_counts = Counter(authors)
        print(f"   Top authors:")
        for author, count in author_counts.most_common(5):
            print(f"     {author}: {count} strategies")
    
    print(f"\n🔍 Enriched Strategies: {len(enriched)}")
    if enriched:
        # Calculate enrichment progress
        progress = (len(enriched) / len(strategies)) * 100 if strategies else 0
        print(f"   Progress: {progress:.1f}% of total strategies")
        
        # Quality metrics
        quality_stats = {
            'description': sum(1 for s in enriched if s.get('description')),
            'ticker': sum(1 for s in enriched if s.get('default_ticker')),
            'timeframe': sum(1 for s in enriched if s.get('default_timeframe')),
            'strategy_type': sum(1 for s in enriched if s.get('strategy_type')),
            'tags': sum(1 for s in enriched if s.get('tags'))
        }
        
        print(f"   Quality metrics:")
        for metric, count in quality_stats.items():
            percentage = (count / len(enriched)) * 100
            print(f"     {metric}: {count}/{len(enriched)} ({percentage:.1f}%)")
        
        # Most common tickers/timeframes
        tickers = [s.get('default_ticker') for s in enriched if s.get('default_ticker')]
        if tickers:
            ticker_counts = Counter(tickers)
            print(f"   Top tickers: {', '.join([f'{t}({c})' for t, c in ticker_counts.most_common(3)])}")
        
        timeframes = [s.get('default_timeframe') for s in enriched if s.get('default_timeframe')]
        if timeframes:
            tf_counts = Counter(timeframes)
            print(f"   Top timeframes: {', '.join([f'{t}({c})' for t, c in tf_counts.most_common(3)])}")
        
        # Strategy types
        types = [s.get('strategy_type') for s in enriched if s.get('strategy_type')]
        if types:
            type_counts = Counter(types)
            print(f"   Strategy types: {', '.join([f'{t}({c})' for t, c in type_counts.items()])}")
    
    print(f"\n⚡ Next Steps:")
    if not enriched:
        print(f"   → Run: python tv_enrich.py --limit 10")
        print(f"   → Start enrichment with a small batch")
    elif len(enriched) < len(strategies):
        remaining = len(strategies) - len(enriched)
        print(f"   → Run: python tv_enrich.py --limit 50")
        print(f"   → Continue enriching ({remaining} strategies remaining)")
    else:
        print(f"   → All strategies enriched!")
        print(f"   → Ready for strategy intelligence analysis")
    
    print(f"\n📁 Files:")
    data_dir = Path(__file__).parent / "data"
    for file_path in data_dir.glob("*.json"):
        size_mb = file_path.stat().st_size / (1024 * 1024)
        print(f"   {file_path.name}: {size_mb:.1f} MB")
    
    # Log files
    log_file = data_dir / "enrich.log"
    if log_file.exists():
        size_kb = log_file.stat().st_size / 1024
        print(f"   enrich.log: {size_kb:.1f} KB")

if __name__ == "__main__":
    main()