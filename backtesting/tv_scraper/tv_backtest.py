#!/usr/bin/env python3
"""
TradingView Strategy Backtester - Phase 2

Automates backtesting of scraped strategies on specified tickers.
Navigates to strategy pages, applies to charts, and extracts performance metrics.
"""

import argparse
import asyncio
import getpass
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional

from playwright.async_api import async_playwright, Page, Browser

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from models import Strategy, BacktestResult, BacktestMetrics, DataManager
from config import *


class TradingViewBacktester:
    """Automates backtesting of TradingView strategies."""
    
    def __init__(self, tickers: List[str] = None, login: bool = False):
        self.tickers = tickers or DEFAULT_TICKERS
        self.login = login
        self.logger = self._setup_logging()
        self.tested_combinations: set = set()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
        return logging.getLogger(__name__)
    
    async def backtest_strategies(self, strategies: List[Strategy], 
                                limit: int = None) -> List[BacktestResult]:
        """
        Main backtesting function.
        
        Args:
            strategies: List of strategies to test
            limit: Maximum number of strategies to test
            
        Returns:
            List of backtest results
        """
        self.logger.info("Starting TradingView strategy backtester")
        self.logger.info(f"Testing {len(strategies[:limit] if limit else strategies)} strategies "
                        f"on {len(self.tickers)} tickers")
        
        # Load existing results for resume functionality
        existing_results = DataManager.load_backtest_results(BACKTEST_RESULTS_FILE)
        self.tested_combinations = {
            (r.strategy_url, r.ticker) for r in existing_results
        }
        self.logger.info(f"Loaded {len(existing_results)} existing backtest results")
        
        results = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(**BROWSER_LAUNCH_SETTINGS)
            context = await browser.new_context(**BROWSER_CONTEXT_SETTINGS)
            page = await context.new_page()
            
            try:
                # Login if required
                if self.login:
                    await self._login(page)
                
                # Test each strategy
                strategies_to_test = strategies[:limit] if limit else strategies
                
                for i, strategy in enumerate(strategies_to_test, 1):
                    self.logger.info(f"Testing strategy {i}/{len(strategies_to_test)}: "
                                   f"{strategy.title}")
                    
                    strategy_results = await self._test_strategy(page, strategy)
                    results.extend(strategy_results)
                    
                    # Save intermediate results periodically
                    if i % 10 == 0:
                        await self._save_intermediate_results(results)
                    
                    # Delay between strategies
                    if i < len(strategies_to_test):
                        await asyncio.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Backtesting failed: {e}")
                raise
            finally:
                await browser.close()
        
        self.logger.info(f"Backtesting completed! Generated {len(results)} new results")
        return results
    
    async def _login(self, page: Page) -> None:
        """Login to TradingView if credentials are provided."""
        username = TV_USERNAME or input("TradingView username: ")
        password = TV_PASSWORD or getpass.getpass("TradingView password: ")
        
        self.logger.info("Logging into TradingView...")
        
        await page.goto(f"{TRADINGVIEW_BASE_URL}/accounts/signin/")
        await page.wait_for_load_state("networkidle")
        
        # Fill login form
        await page.fill('input[name="username"]', username)
        await page.fill('input[name="password"]', password)
        
        # Click login button
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        
        # Wait a bit for login to complete
        await asyncio.sleep(3)
        
        # Check if login was successful
        if "/accounts/signin/" in page.url:
            raise Exception("Login failed - still on signin page")
        
        self.logger.info("✅ Successfully logged in")
    
    async def _test_strategy(self, page: Page, strategy: Strategy) -> List[BacktestResult]:
        """Test a single strategy on all tickers."""
        results = []
        
        try:
            # Navigate to strategy page
            self.logger.info(f"Navigating to: {strategy.script_url}")
            await page.goto(strategy.script_url, wait_until="networkidle")
            await asyncio.sleep(2)
            
            for ticker in self.tickers:
                # Skip if already tested
                if (strategy.script_url, ticker) in self.tested_combinations:
                    self.logger.info(f"  Skipping {ticker} (already tested)")
                    continue
                
                self.logger.info(f"  Testing ticker: {ticker}")
                
                try:
                    result = await self._test_strategy_ticker(page, strategy, ticker)
                    results.append(result)
                    self.tested_combinations.add((strategy.script_url, ticker))
                    
                except Exception as e:
                    self.logger.warning(f"  Failed to test {ticker}: {e}")
                    # Create error result
                    error_result = BacktestResult(
                        strategy_url=strategy.script_url,
                        strategy_title=strategy.title,
                        ticker=ticker,
                        metrics=BacktestMetrics(),
                        success=False,
                        error_message=str(e)
                    )
                    results.append(error_result)
                
                # Small delay between tickers
                await asyncio.sleep(1)
        
        except Exception as e:
            self.logger.error(f"Failed to test strategy {strategy.title}: {e}")
            # Create error results for all tickers
            for ticker in self.tickers:
                if (strategy.script_url, ticker) not in self.tested_combinations:
                    error_result = BacktestResult(
                        strategy_url=strategy.script_url,
                        strategy_title=strategy.title,
                        ticker=ticker,
                        metrics=BacktestMetrics(),
                        success=False,
                        error_message=f"Strategy page error: {e}"
                    )
                    results.append(error_result)
        
        return results
    
    async def _test_strategy_ticker(self, page: Page, strategy: Strategy, 
                                  ticker: str) -> BacktestResult:
        """Test a strategy on a specific ticker."""
        try:
            # Click "Add to Chart" or "Open in Pine Editor" 
            chart_button = None
            
            # Try different possible button texts
            button_texts = ["Add to Chart", "Open in chart", "Apply to chart", "Open in Pine Editor"]
            
            for button_text in button_texts:
                chart_button = page.locator(f"text={button_text}").first
                if await chart_button.count() > 0:
                    break
            
            if not chart_button or await chart_button.count() == 0:
                raise Exception("Could not find 'Add to Chart' button")
            
            await chart_button.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
            
            # Wait for chart to load
            await page.wait_for_selector('.chart-container', timeout=30000)
            
            # Change ticker symbol
            await self._change_ticker(page, ticker)
            
            # Wait for strategy to load on new ticker
            await asyncio.sleep(5)
            
            # Open Strategy Tester panel
            await self._open_strategy_tester(page)
            
            # Extract performance metrics
            metrics = await self._extract_metrics(page)
            
            return BacktestResult(
                strategy_url=strategy.script_url,
                strategy_title=strategy.title,
                ticker=ticker,
                metrics=metrics,
                success=True
            )
            
        except Exception as e:
            raise Exception(f"Backtest failed for {ticker}: {e}")
    
    async def _change_ticker(self, page: Page, ticker: str) -> None:
        """Change the ticker symbol on the chart."""
        try:
            # Look for symbol search box
            symbol_input = page.locator('input[data-name="symbol-search-items-dialog-input"]')
            
            if await symbol_input.count() == 0:
                # Try clicking on the symbol name to open search
                symbol_area = page.locator('.symbol-name').first
                if await symbol_area.count() > 0:
                    await symbol_area.click()
                    await asyncio.sleep(1)
                    symbol_input = page.locator('input[data-name="symbol-search-items-dialog-input"]')
            
            if await symbol_input.count() == 0:
                # Alternative selector
                symbol_input = page.locator('.symbol-edit input').first
            
            if await symbol_input.count() > 0:
                # Clear and type new symbol
                await symbol_input.click()
                await symbol_input.fill("")
                await symbol_input.type(ticker)
                await asyncio.sleep(1)
                
                # Press Enter or click first suggestion
                await page.keyboard.press("Enter")
                await asyncio.sleep(3)
            else:
                raise Exception("Could not find symbol input field")
                
        except Exception as e:
            raise Exception(f"Failed to change ticker to {ticker}: {e}")
    
    async def _open_strategy_tester(self, page: Page) -> None:
        """Open the Strategy Tester panel."""
        try:
            # Look for Strategy Tester tab/button
            tester_buttons = [
                '.icon-strategy-tester',
                'text=Strategy Tester',
                '[data-name="strategy-tester"]',
                '.bottom-panel .tab[data-name*="tester"]'
            ]
            
            clicked = False
            for selector in tester_buttons:
                button = page.locator(selector).first
                if await button.count() > 0:
                    await button.click()
                    clicked = True
                    break
            
            if not clicked:
                # Try opening from menu
                more_menu = page.locator('.more-btn', '.menu-btn').first
                if await more_menu.count() > 0:
                    await more_menu.click()
                    await asyncio.sleep(1)
                    
                    tester_item = page.locator('text=Strategy Tester').first
                    if await tester_item.count() > 0:
                        await tester_item.click()
                        clicked = True
            
            if clicked:
                await asyncio.sleep(2)
                # Wait for panel to open
                await page.wait_for_selector('.strategy-tester', timeout=10000)
            else:
                raise Exception("Could not find Strategy Tester button")
                
        except Exception as e:
            self.logger.warning(f"Could not open Strategy Tester: {e}")
            # Continue anyway as metrics might be visible
    
    async def _extract_metrics(self, page: Page) -> BacktestMetrics:
        """Extract performance metrics from Strategy Tester."""
        metrics = BacktestMetrics()
        
        try:
            # Wait for strategy tester data to load
            await asyncio.sleep(3)
            
            # Look for Performance Summary or similar section
            perf_section = page.locator('.strategy-tester .performance-summary, .backtesting-container')
            
            if await perf_section.count() == 0:
                # Try alternative selectors
                perf_section = page.locator('.strategy-tester')
            
            # Extract metrics by looking for common patterns
            metrics_map = {
                'net_profit': ['Net Profit', 'Total Net Profit', 'P&L'],
                'net_profit_percent': ['Net Profit %', 'Return %', 'Total Return'],
                'max_drawdown': ['Max Drawdown', 'Maximum Drawdown'],
                'max_drawdown_percent': ['Max Drawdown %', 'Max DD %'],
                'sharpe_ratio': ['Sharpe Ratio', 'Sharpe'],
                'sortino_ratio': ['Sortino Ratio', 'Sortino'],
                'profit_factor': ['Profit Factor', 'PF'],
                'total_trades': ['Total Trades', 'Trades', 'Number of Trades'],
                'win_rate_percent': ['Win Rate', 'Win %', 'Winners %'],
                'avg_trade': ['Average Trade', 'Avg Trade', 'Mean Trade'],
                'buy_hold_return': ['Buy & Hold Return', 'B&H Return', 'Buy and Hold']
            }
            
            # Extract each metric
            for field, labels in metrics_map.items():
                for label in labels:
                    try:
                        value = await self._extract_metric_value(page, label)
                        if value is not None:
                            setattr(metrics, field, value)
                            break
                    except Exception:
                        continue
            
        except Exception as e:
            self.logger.warning(f"Failed to extract metrics: {e}")
        
        return metrics
    
    async def _extract_metric_value(self, page: Page, label: str) -> Optional[float]:
        """Extract a specific metric value by label."""
        try:
            # Look for the label and associated value
            selectors = [
                f'text="{label}"',
                f'[data-name*="{label.lower()}"]',
                f'.metric:has-text("{label}")'
            ]
            
            for selector in selectors:
                element = page.locator(selector).first
                if await element.count() > 0:
                    # Get parent or sibling element that might contain the value
                    parent = element.locator('..')
                    text = await parent.text_content()
                    
                    if text:
                        # Parse numeric value from text
                        return self._parse_numeric_value(text)
            
        except Exception:
            pass
        
        return None
    
    def _parse_numeric_value(self, text: str) -> Optional[float]:
        """Parse numeric value from text string."""
        try:
            import re
            
            # Remove common symbols and extract number
            # Handle formats like: "$1,234.56", "12.34%", "(1,234.56)", "+123.45"
            text = text.strip()
            
            # Extract number pattern
            pattern = r'([+-]?\d{1,3}(?:,\d{3})*\.?\d*)'
            matches = re.findall(pattern, text)
            
            if matches:
                # Take the first number found
                num_str = matches[0].replace(',', '')
                value = float(num_str)
                
                # Handle percentages
                if '%' in text:
                    value = value / 100
                
                return value
                
        except Exception:
            pass
        
        return None
    
    async def _save_intermediate_results(self, new_results: List[BacktestResult]) -> None:
        """Save intermediate results to avoid losing progress."""
        try:
            # Load existing results
            existing_results = DataManager.load_backtest_results(BACKTEST_RESULTS_FILE)
            
            # Merge with new results
            all_results = existing_results + new_results
            
            # Save back to file
            DataManager.save_backtest_results(all_results, BACKTEST_RESULTS_FILE)
            
            self.logger.info(f"Saved {len(all_results)} total results to {BACKTEST_RESULTS_FILE}")
            
        except Exception as e:
            self.logger.warning(f"Failed to save intermediate results: {e}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Backtest TradingView strategies")
    parser.add_argument("--strategies-file", default=str(STRATEGIES_FILE),
                       help="Path to strategies JSON file")
    parser.add_argument("--tickers", help="Comma-separated list of tickers (default: SPY,QQQ,AAPL,TSLA,BTC-USD)")
    parser.add_argument("--limit", type=int, help="Maximum number of strategies to test")
    parser.add_argument("--login", action="store_true", help="Login to TradingView")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode (visible browser)")
    
    args = parser.parse_args()
    
    # Parse tickers
    tickers = DEFAULT_TICKERS
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(',')]
    
    # Load strategies
    try:
        strategies = DataManager.load_strategies(args.strategies_file)
        if not strategies:
            print(f"❌ No strategies found in {args.strategies_file}")
            print("Run tv_scrape.py first to collect strategies")
            return 1
    except Exception as e:
        print(f"❌ Failed to load strategies: {e}")
        return 1
    
    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)
    
    # Set debug mode
    if args.debug:
        BROWSER_LAUNCH_SETTINGS["headless"] = False
    
    backtester = TradingViewBacktester(tickers=tickers, login=args.login)
    
    try:
        new_results = await backtester.backtest_strategies(strategies, limit=args.limit)
        
        # Load existing and merge
        existing_results = DataManager.load_backtest_results(BACKTEST_RESULTS_FILE)
        all_results = existing_results + new_results
        
        # Save final results
        DataManager.save_backtest_results(all_results, BACKTEST_RESULTS_FILE)
        
        print(f"\n✅ Backtesting completed!")
        print(f"📊 Total backtest results: {len(all_results)}")
        print(f"🆕 New results generated: {len(new_results)}")
        print(f"💾 Saved to: {BACKTEST_RESULTS_FILE}")
        
        if new_results:
            # Show some statistics
            successful_results = [r for r in new_results if r.success]
            print(f"\n📈 Success rate: {len(successful_results)}/{len(new_results)} "
                  f"({len(successful_results)/len(new_results)*100:.1f}%)")
            
            if successful_results:
                # Show top performers
                profitable = [r for r in successful_results 
                            if r.metrics.net_profit_percent and r.metrics.net_profit_percent > 0]
                
                if profitable:
                    profitable.sort(key=lambda x: x.metrics.net_profit_percent or 0, reverse=True)
                    print(f"\n🔥 Top performing results:")
                    for result in profitable[:5]:
                        print(f"  • {result.strategy_title} on {result.ticker}: "
                              f"{result.metrics.net_profit_percent:.2%} profit")
    
    except KeyboardInterrupt:
        print("\n⚠️  Backtesting interrupted by user")
    except Exception as e:
        print(f"\n❌ Backtesting failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))