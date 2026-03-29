#!/usr/bin/env python3
"""
Validation script for enriched TradingView strategies.
Analyzes the enrichment quality and provides statistics.
"""

import json
import sys
from pathlib import Path
from collections import Counter

def load_enriched_data():
    """Load enriched strategies data."""
    enriched_file = Path(__file__).parent / "data" / "strategies_enriched.json"
    
    if not enriched_file.exists():
        print("❌ No enriched data found. Run tv_enrich.py first.")
        return []
    
    with open(enriched_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_enrichment_quality(strategies):
    """Analyze the quality of enrichment data."""
    if not strategies:
        print("No strategies to analyze.")
        return
    
    total = len(strategies)
    stats = {
        'description': sum(1 for s in strategies if s.get('description')),
        'default_ticker': sum(1 for s in strategies if s.get('default_ticker')),
        'default_timeframe': sum(1 for s in strategies if s.get('default_timeframe')),
        'strategy_type': sum(1 for s in strategies if s.get('strategy_type')),
        'tags': sum(1 for s in strategies if s.get('tags')),
        'pine_version': sum(1 for s in strategies if s.get('pine_version')),
        'publish_date': sum(1 for s in strategies if s.get('publish_date')),
        'performance_data': sum(1 for s in strategies if any(
            v is not None for v in s.get('performance', {}).values()
        )),
        'enrichment_errors': sum(1 for s in strategies if s.get('enrichment_error'))
    }
    
    print(f"\n📊 Enrichment Quality Report")
    print(f"Total strategies: {total}")
    print(f"")
    
    for field, count in stats.items():
        percentage = (count / total) * 100
        status = "✅" if percentage > 70 else "⚠️" if percentage > 30 else "❌"
        print(f"{status} {field}: {count}/{total} ({percentage:.1f}%)")
    
    # Analyze tags distribution
    all_tags = []
    for strategy in strategies:
        tags = strategy.get('tags', [])
        all_tags.extend(tags)
    
    if all_tags:
        print(f"\n🏷️ Top Tags:")
        tag_counts = Counter(all_tags)
        for tag, count in tag_counts.most_common(10):
            print(f"  {tag}: {count}")
    
    # Analyze tickers
    tickers = [s.get('default_ticker') for s in strategies if s.get('default_ticker')]
    if tickers:
        print(f"\n📈 Top Tickers:")
        ticker_counts = Counter(tickers)
        for ticker, count in ticker_counts.most_common(10):
            print(f"  {ticker}: {count}")
    
    # Analyze timeframes
    timeframes = [s.get('default_timeframe') for s in strategies if s.get('default_timeframe')]
    if timeframes:
        print(f"\n⏰ Top Timeframes:")
        tf_counts = Counter(timeframes)
        for tf, count in tf_counts.most_common(10):
            print(f"  {tf}: {count}")
    
    # Analyze strategy types
    types = [s.get('strategy_type') for s in strategies if s.get('strategy_type')]
    if types:
        print(f"\n🎯 Strategy Types:")
        type_counts = Counter(types)
        for stype, count in type_counts.items():
            print(f"  {stype}: {count}")
    
    # Show errors if any
    errors = [s for s in strategies if s.get('enrichment_error')]
    if errors:
        print(f"\n❌ Enrichment Errors ({len(errors)}):")
        for error in errors[:5]:  # Show first 5
            print(f"  {error['title']}: {error.get('enrichment_error', 'Unknown error')}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")

def show_sample_strategy(strategies):
    """Show a sample enriched strategy."""
    if not strategies:
        return
    
    # Find a well-enriched strategy
    best_strategy = None
    best_score = 0
    
    for strategy in strategies:
        score = 0
        if strategy.get('description'): score += 3  # Description is most important
        if strategy.get('default_ticker'): score += 1
        if strategy.get('default_timeframe'): score += 1
        if strategy.get('strategy_type'): score += 1
        if strategy.get('tags'): score += 1
        if strategy.get('pine_version'): score += 1
        
        if score > best_score:
            best_score = score
            best_strategy = strategy
    
    if best_strategy:
        print(f"\n🔍 Sample Well-Enriched Strategy:")
        print(f"Title: {best_strategy.get('title', 'N/A')}")
        print(f"Author: {best_strategy.get('author', 'N/A')}")
        print(f"Boost Count: {best_strategy.get('boost_count', 'N/A')}")
        print(f"Ticker: {best_strategy.get('default_ticker', 'N/A')}")
        print(f"Timeframe: {best_strategy.get('default_timeframe', 'N/A')}")
        print(f"Strategy Type: {best_strategy.get('strategy_type', 'N/A')}")
        print(f"Pine Version: {best_strategy.get('pine_version', 'N/A')}")
        print(f"Tags: {', '.join(best_strategy.get('tags', []))}")
        
        description = best_strategy.get('description', '')
        if description:
            preview = description[:200] + "..." if len(description) > 200 else description
            print(f"Description Preview: {preview}")
        
        performance = best_strategy.get('performance', {})
        if any(v is not None for v in performance.values()):
            print(f"Performance Data Available: Yes")
            for key, value in performance.items():
                if value is not None:
                    print(f"  {key}: {value}")

def main():
    """Main function."""
    print("🔍 TradingView Strategy Enrichment Validator")
    
    strategies = load_enriched_data()
    
    if not strategies:
        return 1
    
    analyze_enrichment_quality(strategies)
    show_sample_strategy(strategies)
    
    print(f"\n✅ Validation completed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())