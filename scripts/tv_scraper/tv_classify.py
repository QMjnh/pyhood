#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
TradingView Strategy Text Classifier

Reads strategies_enriched.json and fills in missing metadata by analyzing 
title + description text. Outputs strategies_classified.json with enhanced metadata.

Usage:
    python tv_classify.py [--input FILE] [--output FILE]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set, Union


class StrategyClassifier:
    """Text-based classifier for TradingView strategies."""
    
    def __init__(self):
        self.setup_patterns()
        self.stats = {
            'tickers_filled': 0,
            'timeframes_filled': 0,
            'total_processed': 0,
            'asset_classes': Counter(),
            'trading_styles': Counter(),
            'regime_tags': Counter(),
            'quality_scores': []
        }
    
    def setup_patterns(self):
        """Initialize regex patterns and lookup tables."""
        
        # Crypto patterns (case insensitive)
        self.crypto_tickers = {
            'BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'ADA', 'AVAX', 'BNB', 'DOT', 
            'MATIC', 'LINK', 'ATOM', 'LTC', 'BCH', 'UNI', 'AAVE', 'COMP',
            'SUSHI', 'CRV', 'YFI', 'SNX', 'MKR', 'USDT', 'USDC', 'BUSD'
        }
        
        # Crypto with pairs (BTCUSDT, ETHUSDT, etc.)
        crypto_pairs = []
        for base in ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'ADA', 'AVAX', 'BNB', 'DOT', 'MATIC', 'LINK', 'ATOM']:
            for quote in ['USDT', 'USDC', 'USD', 'BUSD', 'BTC', 'ETH']:
                crypto_pairs.append(f'{base}{quote}')
        
        # Equity tickers
        self.equity_tickers = {
            'SPY', 'QQQ', 'IWM', 'DIA', 'VTI', 'VOO', 'AAPL', 'TSLA', 'NVDA', 
            'AMZN', 'META', 'MSFT', 'GOOGL', 'GOOG', 'AMD', 'NFLX', 'CRM',
            'BABA', 'UBER', 'COIN', 'PYPL', 'ROKU', 'ZM', 'SHOP', 'SQ',
            'ARKK', 'ARKQ', 'ARKG', 'SPXL', 'TQQQ', 'SOXL'
        }
        
        # Futures tickers
        self.futures_tickers = {
            'ES', 'NQ', 'YM', 'RTY', 'CL', 'GC', 'SI', 'ZB', 'ZN', 'ZF',
            'ES1!', 'NQ1!', 'YM1!', 'RTY1!', 'CL1!', 'GC1!', 'SI1!',
            'MES', 'MNQ', 'MYM', 'M2K', 'MCL', 'MGC', 'SIL'
        }
        
        # Forex pairs
        self.forex_tickers = {
            'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'NZDUSD', 'USDCAD',
            'USDCHF', 'EURJPY', 'GBPJPY', 'AUDJPY', 'EURGBP', 'EURAUD',
            'GBPAUD', 'AUDCAD', 'NZDCAD', 'EURNZD'
        }
        
        # Commodities
        self.commodity_tickers = {
            'XAUUSD', 'XAGUSD', 'XPTUSD', 'XPDUSD', 'USOIL', 'UKOIL',
            'NATGAS', 'COPPER', 'DX1!', 'DXY'
        }
        
        # All tickers combined for regex
        all_tickers = (
            self.crypto_tickers | set(crypto_pairs) | self.equity_tickers | 
            self.futures_tickers | self.forex_tickers | self.commodity_tickers
        )
        
        # Create regex pattern for ticker extraction (word boundaries)
        self.ticker_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(t) for t in sorted(all_tickers, key=len, reverse=True)) + r')\b',
            re.IGNORECASE
        )
        
        # Timeframe patterns
        self.timeframe_patterns = [
            (re.compile(r'\b(\d+)s\b', re.IGNORECASE), lambda m: f"{m.group(1)}s"),
            (re.compile(r'\b(\d+)\s*(?:min|minute)s?\b', re.IGNORECASE), lambda m: f"{m.group(1)}m"),
            (re.compile(r'\b(\d+)m\b', re.IGNORECASE), lambda m: f"{m.group(1)}m"),
            (re.compile(r'\b(\d+)\s*(?:hr|hour)s?\b', re.IGNORECASE), lambda m: f"{m.group(1)}H"),
            (re.compile(r'\b(\d+)H\b', re.IGNORECASE), lambda m: f"{m.group(1)}H"),
            (re.compile(r'\bdaily\b', re.IGNORECASE), lambda m: "1D"),
            (re.compile(r'\b1\s*day\b', re.IGNORECASE), lambda m: "1D"),
            (re.compile(r'\b(\d+)D\b', re.IGNORECASE), lambda m: f"{m.group(1)}D"),
            (re.compile(r'\bweekly\b', re.IGNORECASE), lambda m: "1W"),
            (re.compile(r'\b1\s*week\b', re.IGNORECASE), lambda m: "1W"),
            (re.compile(r'\b(\d+)W\b', re.IGNORECASE), lambda m: f"{m.group(1)}W"),
            (re.compile(r'\bmonthly\b', re.IGNORECASE), lambda m: "1M"),
            (re.compile(r'\b1\s*month\b', re.IGNORECASE), lambda m: "1M"),
        ]
        
        # Regime/market condition patterns
        self.regime_patterns = {
            'trending': [
                re.compile(r'\b(?:trend(?:ing)?|directional|momentum)\b', re.IGNORECASE),
                re.compile(r'\b(?:ema|sma).*cross\b', re.IGNORECASE),
                re.compile(r'\b(?:breakout|break.*out)\b', re.IGNORECASE)
            ],
            'ranging': [
                re.compile(r'\b(?:range|ranging|sideways|consolidat|bound|mean.revert)\b', re.IGNORECASE),
                re.compile(r'\b(?:rsi|bollinger|bb|overbought|oversold)\b', re.IGNORECASE),
                re.compile(r'\b(?:support|resistance|channel)\b', re.IGNORECASE)
            ],
            'high_volatility': [
                re.compile(r'\b(?:high.vol|volatile|volatility|spikes?)\b', re.IGNORECASE),
                re.compile(r'\b(?:vix|fear|panic)\b', re.IGNORECASE)
            ],
            'low_volatility': [
                re.compile(r'\b(?:low.vol|quiet|calm|stable)\b', re.IGNORECASE)
            ],
            'bullish': [
                re.compile(r'\b(?:bull|bullish|uptrend|rising|up.trend)\b', re.IGNORECASE)
            ],
            'bearish': [
                re.compile(r'\b(?:bear|bearish|downtrend|falling|down.trend)\b', re.IGNORECASE)
            ],
            'breakout': [
                re.compile(r'\b(?:breakout|break.*out|burst)\b', re.IGNORECASE)
            ],
            'momentum': [
                re.compile(r'\b(?:momentum|mo|macd|stoch)\b', re.IGNORECASE)
            ]
        }
        
        # Trading style keywords
        self.style_patterns = {
            'scalp': [
                re.compile(r'\b(?:scalp|scalping|seconds?|tick)\b', re.IGNORECASE),
                re.compile(r'\b(?:quick|fast|rapid|instant)\b', re.IGNORECASE)
            ],
            'intraday': [
                re.compile(r'\b(?:intraday|day.trad|same.day|minutes?|hours?)\b', re.IGNORECASE)
            ],
            'swing': [
                re.compile(r'\b(?:swing|days?|multi.day)\b', re.IGNORECASE)
            ],
            'position': [
                re.compile(r'\b(?:position|long.term|weeks?|months?|hold)\b', re.IGNORECASE)
            ]
        }
    
    def extract_ticker(self, text: str) -> Optional[str]:
        """Extract most prominent ticker from text."""
        matches = self.ticker_pattern.findall(text)
        if not matches:
            return None
        
        # Count occurrences and return most frequent
        ticker_counts = Counter(match.upper() for match in matches)
        return ticker_counts.most_common(1)[0][0]
    
    def extract_timeframe(self, text: str) -> Optional[str]:
        """Extract and normalize timeframe from text."""
        for pattern, normalizer in self.timeframe_patterns:
            match = pattern.search(text)
            if match:
                return normalizer(match)
        return None
    
    def determine_asset_class(self, ticker: str, title: str, description: str, tags: List[str]) -> str:
        """Determine asset class from ticker and context."""
        if not ticker:
            # Check tags and text for clues
            safe_title = title or ''
            safe_description = description or ''
            safe_tags = tags or []
            text = (safe_title + ' ' + safe_description + ' ' + ' '.join(safe_tags)).lower()
            
            if any(tag in text for tag in ['usdt', 'crypto', 'bitcoin', 'ethereum', 'btc', 'eth']):
                return 'crypto'
            elif any(tag in text for tag in ['forex', 'eur', 'gbp', 'jpy', 'currency']):
                return 'forex'
            elif any(tag in text for tag in ['futures', 'contracts', 'es1', 'nq1']):
                return 'futures'
            elif any(tag in text for tag in ['stocks', 'equity', 'spy', 'qqq', 'shares']):
                return 'equities'
            elif any(tag in text for tag in ['gold', 'silver', 'oil', 'commodity']):
                return 'commodities'
            else:
                return 'unknown'
        
        ticker = ticker.upper()
        
        if ticker in self.crypto_tickers or any(crypto in ticker for crypto in ['BTC', 'ETH', 'USDT', 'USDC']):
            return 'crypto'
        elif ticker in self.equity_tickers:
            return 'equities'
        elif ticker in self.futures_tickers:
            return 'futures'
        elif ticker in self.forex_tickers:
            return 'forex'
        elif ticker in self.commodity_tickers or 'XAU' in ticker or 'XAG' in ticker:
            return 'commodities'
        else:
            # Multi-asset or unknown
            return 'unknown'
    
    def determine_trading_style(self, timeframe: str, title: str, description: str) -> str:
        """Determine trading style from timeframe and keywords."""
        safe_title = title or ''
        safe_description = description or ''
        text = safe_title + ' ' + safe_description
        
        # Check keywords first
        for style, patterns in self.style_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    return style
        
        # Fall back to timeframe analysis
        if not timeframe:
            return 'unknown'
        
        tf_lower = timeframe.lower()
        
        # Parse timeframe
        if 's' in tf_lower:  # seconds
            return 'scalp'
        elif 'm' in tf_lower:  # minutes
            minutes = int(re.findall(r'\d+', tf_lower)[0]) if re.findall(r'\d+', tf_lower) else 15
            if minutes <= 15:
                return 'scalp'
            elif minutes <= 240:  # 4H = 240m
                return 'intraday'
            else:
                return 'swing'
        elif 'h' in tf_lower:  # hours
            hours = int(re.findall(r'\d+', tf_lower)[0]) if re.findall(r'\d+', tf_lower) else 1
            if hours <= 4:
                return 'intraday'
            else:
                return 'swing'
        elif 'd' in tf_lower:  # days
            return 'swing'
        elif 'w' in tf_lower or 'm' in tf_lower:  # weeks or months
            return 'position'
        else:
            return 'intraday'  # default
    
    def extract_regime_tags(self, title: str, description: str, strategy_type: str, tags: List[str]) -> List[str]:
        """Extract regime/market condition tags from text."""
        safe_title = title or ''
        safe_description = description or ''
        safe_strategy_type = strategy_type or ''
        safe_tags = tags or []
        text = safe_title + ' ' + safe_description + ' ' + safe_strategy_type + ' ' + ' '.join(safe_tags)
        regime_tags = set()
        
        for regime, patterns in self.regime_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    regime_tags.add(regime)
                    break
        
        return list(regime_tags)
    
    def calculate_quality_score(self, strategy: Dict) -> int:
        """Calculate quality score based on data completeness."""
        score = 0
        
        # Has description
        description = strategy.get('description') or ''
        if description and len(description) > 50:
            score += 20
        
        # Has ticker
        if strategy.get('default_ticker'):
            score += 15
        
        # Has timeframe
        if strategy.get('default_timeframe'):
            score += 15
        
        # Has tags
        if strategy.get('tags') and len(strategy['tags']) > 0:
            score += 10
        
        # Boost count
        boost_count = strategy.get('boost_count', 0) or 0
        if boost_count > 100:
            score += 20
        elif boost_count > 50:
            score += 10
        
        # Description length
        description = strategy.get('description') or ''
        desc_len = len(description)
        if desc_len > 200:
            score += 10
        
        # Has performance data
        perf = strategy.get('performance', {}) or {}
        if any(perf.get(key) for key in ['net_profit_pct', 'total_trades', 'win_rate']):
            score += 10
        
        return min(score, 100)  # Cap at 100
    
    def classify_strategy(self, strategy: Dict) -> Dict:
        """Classify a single strategy and return enhanced version."""
        # Create copy to avoid modifying original
        enhanced = strategy.copy()
        
        title = strategy.get('title', '')
        description = strategy.get('description', '')
        tags = strategy.get('tags', []) or []
        strategy_type = strategy.get('strategy_type', '')
        
        # Extract ticker (only if not already filled)
        if not enhanced.get('default_ticker'):
            text_for_ticker = f"{title or ''} {description or ''}"
            extracted_ticker = self.extract_ticker(text_for_ticker)
            if extracted_ticker:
                enhanced['default_ticker'] = extracted_ticker
                self.stats['tickers_filled'] += 1
        
        # Extract timeframe (only if not already filled)
        if not enhanced.get('default_timeframe'):
            text_for_timeframe = f"{title or ''} {description or ''}"
            extracted_timeframe = self.extract_timeframe(text_for_timeframe)
            if extracted_timeframe:
                enhanced['default_timeframe'] = extracted_timeframe
                self.stats['timeframes_filled'] += 1
        
        # Determine asset class
        asset_class = self.determine_asset_class(
            enhanced.get('default_ticker'), title, description, tags
        )
        enhanced['asset_class'] = asset_class
        self.stats['asset_classes'][asset_class] += 1
        
        # Determine trading style
        trading_style = self.determine_trading_style(
            enhanced.get('default_timeframe'), title, description
        )
        enhanced['trading_style'] = trading_style
        self.stats['trading_styles'][trading_style] += 1
        
        # Extract regime tags
        regime_tags = self.extract_regime_tags(title, description, strategy_type, tags)
        enhanced['regime_tags'] = regime_tags
        for tag in regime_tags:
            self.stats['regime_tags'][tag] += 1
        
        # Calculate quality score
        quality_score = self.calculate_quality_score(enhanced)
        enhanced['quality_score'] = quality_score
        self.stats['quality_scores'].append(quality_score)
        
        self.stats['total_processed'] += 1
        
        return enhanced
    
    def classify_strategies(self, strategies: List[Dict]) -> List[Dict]:
        """Classify all strategies."""
        return [self.classify_strategy(strategy) for strategy in strategies]
    
    def print_summary_stats(self):
        """Print summary statistics."""
        print("\n" + "="*60)
        print("CLASSIFICATION SUMMARY")
        print("="*60)
        
        print(f"Total strategies processed: {self.stats['total_processed']}")
        print(f"Tickers filled: {self.stats['tickers_filled']}")
        print(f"Timeframes filled: {self.stats['timeframes_filled']}")
        
        print(f"\nAsset Class Distribution:")
        for asset_class, count in self.stats['asset_classes'].most_common():
            pct = count / self.stats['total_processed'] * 100
            print(f"  {asset_class:12} {count:4d} ({pct:5.1f}%)")
        
        print(f"\nTrading Style Distribution:")
        for style, count in self.stats['trading_styles'].most_common():
            pct = count / self.stats['total_processed'] * 100
            print(f"  {style:12} {count:4d} ({pct:5.1f}%)")
        
        print(f"\nRegime Tags Distribution:")
        for tag, count in self.stats['regime_tags'].most_common():
            pct = count / self.stats['total_processed'] * 100
            print(f"  {tag:15} {count:4d} ({pct:5.1f}%)")
        
        if self.stats['quality_scores']:
            avg_quality = sum(self.stats['quality_scores']) / len(self.stats['quality_scores'])
            print(f"\nQuality Score: {avg_quality:.1f} average")
            high_quality = sum(1 for score in self.stats['quality_scores'] if score >= 70)
            print(f"High quality (≥70): {high_quality}/{len(self.stats['quality_scores'])} ({high_quality/len(self.stats['quality_scores'])*100:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description='Classify TradingView strategies from text analysis')
    parser.add_argument('--input', 
                       default='~/Projects/pyhood/scripts/tv_scraper/data/strategies_enriched.json',
                       help='Input JSON file (default: strategies_enriched.json)')
    parser.add_argument('--output',
                       default='~/Projects/pyhood/scripts/tv_scraper/data/strategies_classified.json', 
                       help='Output JSON file (default: strategies_classified.json)')
    
    args = parser.parse_args()
    
    # Expand paths
    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()
    
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Loading strategies from: {input_path}")
    try:
        with open(input_path, 'r') as f:
            strategies = json.load(f)
    except Exception as e:
        print(f"Error loading input file: {e}")
        sys.exit(1)
    
    if not isinstance(strategies, list):
        print("Error: Input file should contain a list of strategies")
        sys.exit(1)
    
    print(f"Loaded {len(strategies)} strategies")
    
    # Initialize classifier and process
    classifier = StrategyClassifier()
    print("Classifying strategies...")
    
    classified_strategies = classifier.classify_strategies(strategies)
    
    # Save results
    print(f"Saving classified strategies to: {output_path}")
    try:
        with open(output_path, 'w') as f:
            json.dump(classified_strategies, f, indent=2)
    except Exception as e:
        print(f"Error saving output file: {e}")
        sys.exit(1)
    
    # Print summary
    classifier.print_summary_stats()
    print(f"\nClassified data saved to: {output_path}")


if __name__ == '__main__':
    main()