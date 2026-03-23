#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
TradingView Strategy Metadata Enrichment Scraper

Visits each strategy's script_url and extracts rich metadata including:
- Description text
- Default ticker/timeframe  
- Strategy type
- Performance metrics
- Tags and Pine Script version
- Publish date

For use in a strategy intelligence engine to understand market regime preferences.
"""

import argparse
import asyncio
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page, Browser

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from models import Strategy, DataManager
from config import *


class StrategyEnricher:
    """Enriches scraped TradingView strategies with detailed metadata."""
    
    def __init__(self, delay: float = 3.0):
        self.delay = delay
        self.logger = self._setup_logging()
        self.enriched_count = 0
        self.error_count = 0
        self.start_time = time.time()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        # Create logs directory if it doesn't exist
        log_dir = DATA_DIR
        log_dir.mkdir(exist_ok=True)
        
        # Setup file handler
        log_file = log_dir / "enrich.log"
        
        # Configure logger
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # File handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(LOG_FORMAT)
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    async def enrich_strategies(self, limit: int = None, start_from: int = 0) -> List[Dict[str, Any]]:
        """
        Main enrichment function.
        
        Args:
            limit: Maximum number of strategies to enrich (None = all)
            start_from: Index to start from (for resuming)
            
        Returns:
            List of enriched strategy dictionaries
        """
        self.logger.info("Starting TradingView strategy enrichment")
        self.logger.info(f"Config - Delay: {self.delay}s, Limit: {limit or 'All'}, Start from: {start_from}")
        
        # Load existing strategies
        strategies = DataManager.load_strategies(STRATEGIES_FILE)
        self.logger.info(f"Loaded {len(strategies)} strategies from {STRATEGIES_FILE}")
        
        if not strategies:
            self.logger.error("No strategies found to enrich!")
            return []
        
        # Load existing enriched data for resume functionality
        enriched_file = DATA_DIR / "strategies_enriched.json"
        enriched_strategies = self._load_enriched_strategies(enriched_file)
        enriched_urls = {s.get('script_url', '') for s in enriched_strategies}
        
        self.logger.info(f"Found {len(enriched_strategies)} already enriched strategies")
        
        # Filter strategies to process
        strategies_to_process = []
        for i, strategy in enumerate(strategies):
            if i < start_from:
                continue
            if strategy.script_url in enriched_urls:
                continue  # Already enriched
            strategies_to_process.append((i, strategy))
            if limit and len(strategies_to_process) >= limit:
                break
        
        self.logger.info(f"Processing {len(strategies_to_process)} strategies")
        
        if not strategies_to_process:
            self.logger.info("No strategies to process (all already enriched or outside range)")
            return enriched_strategies
        
        # Start enrichment process
        async with async_playwright() as p:
            browser = await p.chromium.launch(**BROWSER_LAUNCH_SETTINGS)
            context = await browser.new_context(**BROWSER_CONTEXT_SETTINGS)
            page = await context.new_page()
            
            # Set a reasonable timeout
            page.set_default_timeout(30000)
            
            try:
                for idx, (original_idx, strategy) in enumerate(strategies_to_process):
                    self.logger.info(f"Processing strategy {idx + 1}/{len(strategies_to_process)} "
                                   f"(#{original_idx}): {strategy.title}")
                    
                    try:
                        enriched = await self._enrich_single_strategy(page, strategy)
                        if enriched:
                            enriched_strategies.append(enriched)
                            self.enriched_count += 1
                            
                            # Save progress every 10 strategies
                            if self.enriched_count % 10 == 0:
                                self._save_enriched_strategies(enriched_strategies, enriched_file)
                                self.logger.info(f"Progress saved: {self.enriched_count} enriched")
                        else:
                            self.error_count += 1
                            
                    except Exception as e:
                        self.logger.error(f"Failed to enrich strategy {strategy.title}: {e}")
                        self.error_count += 1
                        
                        # Add failed strategy with basic info and error flag
                        failed_entry = strategy.to_dict()
                        failed_entry.update({
                            "enriched_at": datetime.now().isoformat(),
                            "enrichment_error": str(e),
                            "description": None,
                            "default_ticker": None,
                            "default_timeframe": None,
                            "strategy_type": None,
                            "tags": [],
                            "pine_version": None,
                            "publish_date": None,
                            "performance": {}
                        })
                        enriched_strategies.append(failed_entry)
                    
                    # Rate limiting
                    if idx < len(strategies_to_process) - 1:  # Don't wait after the last one
                        self.logger.debug(f"Waiting {self.delay}s before next strategy...")
                        await asyncio.sleep(self.delay)
                
            finally:
                await browser.close()
        
        # Save final results
        self._save_enriched_strategies(enriched_strategies, enriched_file)
        
        elapsed = time.time() - self.start_time
        self.logger.info(f"Enrichment completed! Processed {self.enriched_count} successfully, "
                        f"{self.error_count} errors in {elapsed:.1f}s")
        
        return enriched_strategies
    
    async def _enrich_single_strategy(self, page: Page, strategy: Strategy) -> Optional[Dict[str, Any]]:
        """Enrich a single strategy with detailed metadata."""
        try:
            # Navigate to strategy page
            await page.goto(strategy.script_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)  # Let dynamic content load
            
            # Extract enrichment data
            enriched = strategy.to_dict()
            enriched["enriched_at"] = datetime.now().isoformat()
            
            # Extract description
            enriched["description"] = await self._extract_description(page)
            
            # Extract ticker and timeframe from chart
            ticker, timeframe = await self._extract_chart_info(page)
            enriched["default_ticker"] = ticker
            enriched["default_timeframe"] = timeframe
            
            # Extract strategy type
            enriched["strategy_type"] = await self._extract_strategy_type(page)
            
            # Extract tags
            enriched["tags"] = await self._extract_tags(page)
            
            # Extract Pine Script version
            enriched["pine_version"] = await self._extract_pine_version(page)
            
            # Extract publish date
            enriched["publish_date"] = await self._extract_publish_date(page)
            
            # Extract performance metrics
            enriched["performance"] = await self._extract_performance_metrics(page)
            
            self.logger.debug(f"Successfully enriched: {strategy.title}")
            return enriched
            
        except Exception as e:
            self.logger.error(f"Error enriching {strategy.title}: {e}")
            raise
    
    async def _extract_description(self, page: Page) -> Optional[str]:
        """Extract the strategy description text."""
        try:
            # TradingView strategy descriptions are typically in divs with classes containing 'publication'
            description_selectors = [
                "[class*='publication'] [class*='description']",
                "[class*='publication-description']",
                "[class*='script-description']",
                ".js-content__description",
                "[data-name='description']",
                ".description-content",
                # Fallback: look for divs with substantial text content
                "main div[class*='content'] div[class*='text']:has(p)",
                "main div[class*='publication'] div:has(p)",
            ]
            
            for selector in description_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        text = await element.text_content(timeout=5000)
                        if text and len(text.strip()) > 50:  # Ensure it's substantial content
                            return text.strip()
                except:
                    continue
            
            # Broader search for substantial paragraphs
            paragraphs = page.locator("main p, article p")
            count = await paragraphs.count()
            
            description_parts = []
            for i in range(min(count, 10)):  # Check first 10 paragraphs
                try:
                    p = paragraphs.nth(i)
                    text = await p.text_content(timeout=2000)
                    if text and len(text.strip()) > 30:
                        description_parts.append(text.strip())
                except:
                    continue
            
            if description_parts:
                return "\n\n".join(description_parts)
                
        except Exception as e:
            self.logger.debug(f"Error extracting description: {e}")
        
        return None
    
    async def _extract_chart_info(self, page: Page) -> tuple[Optional[str], Optional[str]]:
        """Extract default ticker and timeframe from chart."""
        ticker = None
        timeframe = None
        
        try:
            # Look for ticker symbol in chart header or symbol selector
            ticker_selectors = [
                "[data-name='legend-source-title']",
                "[class*='symbol-title']",
                "[class*='chart-title']",
                "[data-name='symbol-info']",
                ".symbol-name",
                "[class*='ticker-name']"
            ]
            
            for selector in ticker_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        text = await element.text_content(timeout=3000)
                        if text:
                            # Extract ticker symbol (usually all caps, possibly with numbers)
                            match = re.search(r'\b([A-Z]{2,6}(?:\d+)?(?:USDT?|USD)?)\b', text)
                            if match:
                                ticker = match.group(1)
                                break
                except:
                    continue
            
            # Look for timeframe in chart controls
            timeframe_selectors = [
                "[data-name='time-interval']",
                "[class*='timeframe']",
                "[class*='interval']",
                ".time-interval",
                "[class*='chart-interval']"
            ]
            
            for selector in timeframe_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        text = await element.text_content(timeout=3000)
                        if text:
                            # Extract timeframe (patterns like 1D, 4H, 15m, etc.)
                            match = re.search(r'\b(\d+[mhdwMY]|1H|4H|1D|1W|1M)\b', text, re.IGNORECASE)
                            if match:
                                timeframe = match.group(1)
                                break
                except:
                    continue
            
            # Fallback: look in page text for common ticker/timeframe patterns
            if not ticker or not timeframe:
                try:
                    page_text = await page.locator("body").text_content(timeout=5000)
                    if page_text:
                        if not ticker:
                            # Look for common crypto and stock symbols
                            ticker_match = re.search(r'\b(BTC(?:USDT?)?|ETH(?:USDT?)?|SPY|QQQ|AAPL|TSLA|NQ1?!?|ES1?!?)\b', 
                                                   page_text, re.IGNORECASE)
                            if ticker_match:
                                ticker = ticker_match.group(1).upper()
                        
                        if not timeframe:
                            # Look for timeframe mentions
                            tf_match = re.search(r'\b(\d+(?:min|m|hour|h|day|d|week|w|month|M))\b', 
                                               page_text, re.IGNORECASE)
                            if tf_match:
                                timeframe = tf_match.group(1)
                except:
                    pass
                    
        except Exception as e:
            self.logger.debug(f"Error extracting chart info: {e}")
        
        return ticker, timeframe
    
    async def _extract_strategy_type(self, page: Page) -> Optional[str]:
        """Extract strategy type (long_only, short_only, long_and_short)."""
        try:
            # Look for strategy settings or description mentioning long/short
            page_text = await page.locator("body").text_content(timeout=5000)
            
            if page_text:
                page_text_lower = page_text.lower()
                
                # Check for specific indicators
                has_long = any(term in page_text_lower for term in [
                    'long only', 'long-only', 'long positions', 'buy only', 'long side'
                ])
                has_short = any(term in page_text_lower for term in [
                    'short only', 'short-only', 'short positions', 'sell only', 'short side'
                ])
                has_both = any(term in page_text_lower for term in [
                    'long and short', 'long & short', 'long/short', 'both sides', 
                    'bidirectional', 'buy and sell'
                ])
                
                if has_both or (has_long and has_short):
                    return "long_and_short"
                elif has_long and not has_short:
                    return "long_only"
                elif has_short and not has_long:
                    return "short_only"
                elif 'strategy' in page_text_lower:
                    # Default assumption for strategies is long_and_short
                    return "long_and_short"
                    
        except Exception as e:
            self.logger.debug(f"Error extracting strategy type: {e}")
        
        return None
    
    async def _extract_tags(self, page: Page) -> List[str]:
        """Extract tags/categories applied to the strategy."""
        tags = []
        
        try:
            # Look for tag elements
            tag_selectors = [
                "[class*='tag']",
                "[class*='label']",
                "[class*='category']",
                "[data-name='tags']",
                ".chip",
                ".badge"
            ]
            
            for selector in tag_selectors:
                try:
                    elements = page.locator(selector)
                    count = await elements.count()
                    
                    for i in range(min(count, 20)):  # Limit to 20 tags
                        element = elements.nth(i)
                        text = await element.text_content(timeout=2000)
                        if text and len(text.strip()) < 30:  # Tags should be short
                            tag = text.strip().lower()
                            if tag and tag not in tags:
                                tags.append(tag)
                except:
                    continue
            
            # Look for hashtags in description
            try:
                description = await self._extract_description(page)
                if description:
                    hashtags = re.findall(r'#(\w+)', description)
                    for tag in hashtags:
                        if tag.lower() not in tags:
                            tags.append(tag.lower())
            except:
                pass
                
        except Exception as e:
            self.logger.debug(f"Error extracting tags: {e}")
        
        return tags[:10]  # Limit to 10 tags
    
    async def _extract_pine_version(self, page: Page) -> Optional[str]:
        """Extract Pine Script version (v5, v4, etc.)."""
        try:
            page_text = await page.locator("body").text_content(timeout=5000)
            
            if page_text:
                # Look for version patterns
                version_match = re.search(r'pine\s*script\s*[®™]?\s*v?(\d+)', page_text, re.IGNORECASE)
                if version_match:
                    return f"v{version_match.group(1)}"
                
                # Look for //@version= comments that might be visible
                version_comment = re.search(r'//@version\s*=\s*(\d+)', page_text)
                if version_comment:
                    return f"v{version_comment.group(1)}"
                    
        except Exception as e:
            self.logger.debug(f"Error extracting Pine version: {e}")
        
        return None
    
    async def _extract_publish_date(self, page: Page) -> Optional[str]:
        """Extract strategy publish date."""
        try:
            # Look for publication date elements
            date_selectors = [
                "[class*='publish']",
                "[class*='date']",
                "[class*='time']",
                "time",
                "[datetime]"
            ]
            
            for selector in date_selectors:
                try:
                    elements = page.locator(selector)
                    count = await elements.count()
                    
                    for i in range(min(count, 5)):
                        element = elements.nth(i)
                        
                        # Try datetime attribute first
                        datetime_attr = await element.get_attribute("datetime", timeout=1000)
                        if datetime_attr:
                            # Parse and format as date
                            try:
                                dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                                return dt.strftime('%Y-%m-%d')
                            except:
                                pass
                        
                        # Try text content
                        text = await element.text_content(timeout=1000)
                        if text:
                            # Look for date patterns
                            date_patterns = [
                                r'(\d{4}-\d{2}-\d{2})',
                                r'(\d{1,2}/\d{1,2}/\d{4})',
                                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})'
                            ]
                            
                            for pattern in date_patterns:
                                match = re.search(pattern, text)
                                if match:
                                    return match.group(1)
                except:
                    continue
                    
        except Exception as e:
            self.logger.debug(f"Error extracting publish date: {e}")
        
        return None
    
    async def _extract_performance_metrics(self, page: Page) -> Dict[str, Optional[float]]:
        """Extract performance metrics from Strategy Tester tab."""
        metrics = {
            "net_profit_pct": None,
            "net_profit_usd": None,
            "total_trades": None,
            "win_rate": None,
            "profit_factor": None,
            "max_drawdown_pct": None,
            "sharpe_ratio": None
        }
        
        try:
            # Try to find and click Strategy Tester tab
            strategy_tester_selectors = [
                "text=Strategy Tester",
                "text=Backtest",
                "[data-name='strategy-tester']",
                "[class*='strategy-tester']"
            ]
            
            for selector in strategy_tester_selectors:
                try:
                    tab = page.locator(selector).first
                    if await tab.count() > 0:
                        await tab.click(timeout=5000)
                        await asyncio.sleep(2)  # Wait for tab content to load
                        break
                except:
                    continue
            
            # Extract metrics from the page
            page_text = await page.locator("body").text_content(timeout=5000)
            
            if page_text:
                # Look for common performance metric patterns
                metric_patterns = {
                    "net_profit_pct": [
                        r'net\s+profit[:\s]+([+-]?\d+\.?\d*)%',
                        r'total\s+return[:\s]+([+-]?\d+\.?\d*)%'
                    ],
                    "net_profit_usd": [
                        r'net\s+profit[:\s]+\$?\s*([+-]?\d+\.?\d*)',
                        r'profit[:\s]+\$\s*([+-]?\d+\.?\d*)'
                    ],
                    "total_trades": [
                        r'total\s+trades[:\s]+(\d+)',
                        r'trades[:\s]+(\d+)'
                    ],
                    "win_rate": [
                        r'win\s+rate[:\s]+(\d+\.?\d*)%',
                        r'winning\s+rate[:\s]+(\d+\.?\d*)%'
                    ],
                    "profit_factor": [
                        r'profit\s+factor[:\s]+(\d+\.?\d*)',
                        r'pf[:\s]+(\d+\.?\d*)'
                    ],
                    "max_drawdown_pct": [
                        r'max\s+drawdown[:\s]+([+-]?\d+\.?\d*)%',
                        r'drawdown[:\s]+([+-]?\d+\.?\d*)%'
                    ],
                    "sharpe_ratio": [
                        r'sharpe\s+ratio[:\s]+(\d+\.?\d*)',
                        r'sharpe[:\s]+(\d+\.?\d*)'
                    ]
                }
                
                for metric_name, patterns in metric_patterns.items():
                    for pattern in patterns:
                        match = re.search(pattern, page_text, re.IGNORECASE)
                        if match:
                            try:
                                value = float(match.group(1))
                                metrics[metric_name] = value
                                break
                            except ValueError:
                                continue
                                
        except Exception as e:
            self.logger.debug(f"Error extracting performance metrics: {e}")
        
        return metrics
    
    def _load_enriched_strategies(self, filepath: Path) -> List[Dict[str, Any]]:
        """Load existing enriched strategies."""
        try:
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Error loading enriched strategies: {e}")
        return []
    
    def _save_enriched_strategies(self, strategies: List[Dict[str, Any]], filepath: Path) -> None:
        """Save enriched strategies to JSON file."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(strategies, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving enriched strategies: {e}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Enrich TradingView strategies with metadata")
    parser.add_argument("--limit", type=int, help="Maximum number of strategies to enrich")
    parser.add_argument("--delay", type=float, default=3.0,
                       help="Delay between requests in seconds (default: 3.0)")
    parser.add_argument("--start-from", type=int, default=0,
                       help="Index to start from (for resuming, default: 0)")
    parser.add_argument("--debug", action="store_true", 
                       help="Run in debug mode (visible browser)")
    
    args = parser.parse_args()
    
    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)
    
    # Set debug mode
    if args.debug:
        BROWSER_LAUNCH_SETTINGS["headless"] = False
    
    enricher = StrategyEnricher(delay=args.delay)
    
    try:
        enriched_strategies = await enricher.enrich_strategies(
            limit=args.limit,
            start_from=args.start_from
        )
        
        enriched_file = DATA_DIR / "strategies_enriched.json"
        
        print(f"\n✅ Enrichment completed!")
        print(f"📊 Total enriched strategies: {len(enriched_strategies)}")
        print(f"✅ Successfully enriched: {enricher.enriched_count}")
        print(f"❌ Errors encountered: {enricher.error_count}")
        print(f"💾 Saved to: {enriched_file}")
        
        # Show sample of enriched data
        if enriched_strategies:
            print(f"\n🔍 Sample enriched strategy:")
            sample = enriched_strategies[-1]  # Show the last one processed
            print(f"  Title: {sample.get('title', 'N/A')}")
            print(f"  Author: {sample.get('author', 'N/A')}")
            print(f"  Ticker: {sample.get('default_ticker', 'N/A')}")
            print(f"  Timeframe: {sample.get('default_timeframe', 'N/A')}")
            print(f"  Strategy Type: {sample.get('strategy_type', 'N/A')}")
            print(f"  Tags: {', '.join(sample.get('tags', []))}")
            print(f"  Pine Version: {sample.get('pine_version', 'N/A')}")
            
            performance = sample.get('performance', {})
            if any(v is not None for v in performance.values()):
                print(f"  Performance:")
                for key, value in performance.items():
                    if value is not None:
                        print(f"    {key}: {value}")
    
    except KeyboardInterrupt:
        print("\n⚠️  Enrichment interrupted by user")
    except Exception as e:
        print(f"\n❌ Enrichment failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))