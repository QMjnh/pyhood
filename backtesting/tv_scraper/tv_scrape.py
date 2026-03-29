#!/usr/bin/env python3
"""
TradingView Strategy Scraper - Phase 1

Scrapes TradingView's community strategies page to collect strategy metadata.
Supports pagination, rate limiting, and resume functionality.
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import List, Set
from urllib.parse import urljoin, urlparse, parse_qs

from playwright.async_api import async_playwright, Page, Browser
import json

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from models import Strategy, DataManager
from config import *


class TradingViewScraper:
    """Scrapes TradingView strategies using Playwright."""
    
    def __init__(self, min_boosts: int = DEFAULT_MIN_BOOSTS, 
                 page_delay: float = DEFAULT_PAGE_DELAY):
        self.min_boosts = min_boosts
        self.page_delay = page_delay
        self.scraped_urls: Set[str] = set()
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
        return logging.getLogger(__name__)
    
    async def scrape_strategies(self, max_pages: int = None, 
                              editors_picks: bool = False) -> List[Strategy]:
        """
        Main scraping function.
        
        Args:
            max_pages: Maximum number of pages to scrape (None = all)
            editors_picks: Whether to scrape editors' picks tab instead
            
        Returns:
            List of scraped strategies
        """
        self.logger.info("Starting TradingView strategy scraper")
        self.logger.info(f"Config - Min boosts: {self.min_boosts}, "
                        f"Page delay: {self.page_delay}s, "
                        f"Max pages: {max_pages or 'All'}")
        
        # Load existing data for resume functionality
        existing_strategies = DataManager.load_strategies(STRATEGIES_FILE)
        self.scraped_urls = {s.script_url for s in existing_strategies}
        self.logger.info(f"Loaded {len(existing_strategies)} existing strategies")
        
        strategies = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(**BROWSER_LAUNCH_SETTINGS)
            context = await browser.new_context(**BROWSER_CONTEXT_SETTINGS)
            page = await context.new_page()
            
            try:
                # Navigate to strategies page
                await self._navigate_to_strategies(page, editors_picks)
                
                # Wait for page to load and check total pages
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2)
                
                # Get total pages info
                total_pages = await self._get_total_pages(page)
                if total_pages:
                    self.logger.info(f"Found {total_pages} total pages")
                    if max_pages:
                        total_pages = min(total_pages, max_pages)
                
                # Scrape pages using direct URL navigation
                total = total_pages if total_pages else 100
                for current_page in range(1, total + 1):
                    self.logger.info(f"Scraping page {current_page}/{total}")
                    
                    # Navigate directly to page URL
                    if current_page == 1:
                        page_url = f"{STRATEGIES_URL}"
                    else:
                        page_url = (
                            f"{TRADINGVIEW_BASE_URL}/scripts/"
                            f"page-{current_page}/?script_type=strategies"
                        )
                    
                    await page.goto(page_url, wait_until="domcontentloaded")
                    
                    # Scrape current page
                    page_strategies = await self._scrape_page(page)
                    new_strategies = [s for s in page_strategies 
                                    if s.script_url not in self.scraped_urls]
                    
                    strategies.extend(new_strategies)
                    
                    for strategy in new_strategies:
                        self.scraped_urls.add(strategy.script_url)
                    
                    self.logger.info(
                        f"Page {current_page}: Found {len(page_strategies)}"
                        f" strategies, {len(new_strategies)} new"
                    )
                    
                    # Save after each page for crash safety
                    if new_strategies:
                        existing = DataManager.load_strategies(STRATEGIES_FILE)
                        existing_urls = {s.script_url for s in existing}
                        merged = existing + [
                            s for s in strategies
                            if s.script_url not in existing_urls
                        ]
                        DataManager.save_strategies(merged, STRATEGIES_FILE)
                    
                    # Stop if page returned no results
                    if len(page_strategies) == 0:
                        self.logger.info("Empty page — end of results")
                        break
                    
                    # Check if we should continue
                    if max_pages and current_page >= max_pages:
                        self.logger.info(
                            f"Reached max pages limit ({max_pages})"
                        )
                        break
                    
                    # Rate limiting delay
                    self.logger.info(
                        f"Waiting {self.page_delay}s before next page..."
                    )
                    await asyncio.sleep(self.page_delay)
                
            except Exception as e:
                self.logger.error(f"Scraping failed: {e}")
                raise
            finally:
                await browser.close()
        
        self.logger.info(f"Scraping completed! Found {len(strategies)} new strategies")
        return strategies
    
    async def _navigate_to_strategies(self, page: Page, editors_picks: bool) -> None:
        """Navigate to the strategies page."""
        url = STRATEGIES_URL
        self.logger.info(f"Navigating to {url}")
        
        await page.goto(url, wait_until="networkidle")
        
        if editors_picks:
            self.logger.info("Switching to Editors' picks tab")
            # Look for the editors' picks tab and click it
            try:
                # Wait for tab to be available and click
                editors_tab = page.locator("text=Editor's pick").first
                await editors_tab.wait_for(timeout=10000)
                await editors_tab.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(2)
            except Exception as e:
                self.logger.warning(f"Could not find/click Editors' picks tab: {e}")
    
    async def _get_total_pages(self, page: Page) -> int:
        """Extract total number of pages from pagination."""
        try:
            # Give more time for pagination to load
            await asyncio.sleep(5)
            
            # Look for pagination info with multiple selectors
            pagination_selectors = [
                ".tv-feed__pagination",
                ".paginator",
                ".pagination",
                "[data-name='pagination']"
            ]
            
            for selector in pagination_selectors:
                try:
                    page_info = await page.locator(selector).text_content(timeout=5000)
                    if page_info and "of" in page_info:
                        # Extract number after "of"
                        parts = page_info.split("of")
                        if len(parts) > 1:
                            return int(parts[1].strip().split()[0])
                except:
                    continue
            
            # Alternative: look for last page number in pagination
            button_selectors = [
                ".tv-feed__pagination-pages .tv-button",
                ".pagination .page-button",
                ".paginator button"
            ]
            
            for selector in button_selectors:
                try:
                    buttons = page.locator(selector)
                    count = await buttons.count()
                    if count > 0:
                        last_btn = buttons.last
                        text = await last_btn.text_content(timeout=2000)
                        if text and text.strip().isdigit():
                            return int(text.strip())
                except:
                    continue
                    
        except Exception as e:
            self.logger.warning(f"Could not determine total pages: {e}")
        
        return None
    
    async def _scrape_page(self, page: Page) -> List[Strategy]:
        """Scrape strategies from current page."""
        strategies = []
        
        # Wait for strategy containers to load
        await asyncio.sleep(3)
        
        # Use article elements as strategy containers
        articles = page.locator("article")
        await asyncio.sleep(2)  # Give time for dynamic content
        
        count = await articles.count()
        if count == 0:
            self.logger.warning("Could not find any article containers on page")
            return strategies
        
        self.logger.debug(f"Found {count} article containers on page")
        
        for i in range(count):
            try:
                article = articles.nth(i)
                strategy = await self._extract_strategy_info(article)
                
                if strategy and strategy.boost_count >= self.min_boosts:
                    strategies.append(strategy)
                    
            except Exception as e:
                self.logger.warning(f"Failed to extract strategy {i}: {e}")
                continue
        
        return strategies
    
    async def _extract_strategy_info(self, article) -> Strategy:
        """Extract strategy information from an article container."""
        try:
            # 1. Find the first script link for title and URL
            script_link = article.locator("a[href*='/script/']").first
            if await script_link.count() == 0:
                return None
            
            title = await script_link.text_content(timeout=3000)
            href = await script_link.get_attribute("href", timeout=3000)
            
            if not href or not title:
                return None
                
            script_url = urljoin(TRADINGVIEW_BASE_URL, href)
            title = title.strip()
            
            # 2. Find author link (href contains '/u/')
            author = "Unknown"
            try:
                author_link = article.locator("a[href*='/u/']").first
                if await author_link.count() > 0:
                    author_text = await author_link.text_content(timeout=3000)
                    if author_text:
                        author = author_text.strip()
                        # Strip "by " prefix if present
                        if author.startswith("by "):
                            author = author[3:]
            except:
                pass
            
            # 3. Find boost count from the last button in the article
            # In headless mode, the boost button just shows a number
            # like "29" or "1 K" — it's the last button in the article
            boost_count = 0
            try:
                buttons = article.locator("button")
                button_count = await buttons.count()

                if button_count > 0:
                    # Boost button is the last one in the article
                    last_btn = buttons.nth(button_count - 1)
                    btn_text = await last_btn.text_content(
                        timeout=1000
                    )
                    if btn_text:
                        btn_text = btn_text.strip()
                        # Parse if it looks like a number
                        # (digits, K, M, spaces between digits)
                        import re
                        cleaned = re.sub(r'\s+', '', btn_text)
                        if re.match(
                            r'^\d+[km]?$', cleaned, re.IGNORECASE
                        ):
                            boost_count = self._parse_boost_count(
                                cleaned
                            )
            except Exception as e:
                self.logger.debug(f"Error getting boost count: {e}")
                pass
            
            # 4. Get type label - look for "Pine Script® strategy" or similar
            type_label = "Strategy"  # Default
            try:
                # Look for text containing "Pine Script" or "strategy"
                all_text = await article.text_content(timeout=2000)
                if "Pine Script® strategy" in all_text:
                    type_label = "Pine Script® strategy"
                elif "Pine Script®" in all_text:
                    type_label = "Pine Script®"
            except:
                pass
            
            return Strategy(
                title=title,
                url=script_url,
                author=author,
                boost_count=boost_count,
                type_label=type_label,
                script_url=script_url
            )
            
        except Exception as e:
            self.logger.warning(f"Error extracting strategy info: {e}")
            return None
    

    
    def _parse_boost_count(self, boost_text: str) -> int:
        """Parse boost count text from buttons like '26 boosts 2 6' or '1.2k boosts'."""
        try:
            boost_text = boost_text.lower().strip()
            
            import re
            
            # Look for pattern "X boosts" where X is the number before "boost"
            boost_pattern = re.search(r'(\d+(?:\.\d+)?[km]?)\s*boost', boost_text)
            if boost_pattern:
                number_str = boost_pattern.group(1)
            else:
                # Fallback: extract the first number found
                number_match = re.search(r'(\d+(?:\.\d+)?[km]?)', boost_text)
                if not number_match:
                    return 0
                number_str = number_match.group(1)
            
            # Handle suffixes
            if number_str.endswith('k'):
                return int(float(number_str[:-1]) * 1000)
            elif number_str.endswith('m'):
                return int(float(number_str[:-1]) * 1000000)
            else:
                # Remove commas and convert
                clean_number = number_str.replace(',', '')
                return int(float(clean_number))
        except (ValueError, AttributeError):
            return 0
    
    async def _go_to_next_page(self, page: Page) -> bool:
        """Navigate to next page. Returns True if successful."""
        try:
            # Multiple strategies for finding "Next" button
            next_selectors = [
                "a:has-text('Next')",
                "button:has-text('Next')",
                "[aria-label='Next page']",
                "[title='Next page']",
                ".next-page",
                "a[href*='offset=']",  # TradingView often uses offset pagination
            ]
            
            next_btn = None
            for selector in next_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.count() > 0:
                        next_btn = btn
                        self.logger.debug(f"Found next button with selector: {selector}")
                        break
                except:
                    continue
            
            if not next_btn:
                # Try to find pagination by looking for numbered links
                # and clicking the next number
                current_url = page.url
                self.logger.debug(f"Current URL: {current_url}")
                
                # Look for offset in URL
                if 'offset=' in current_url:
                    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
                    parsed = urlparse(current_url)
                    query_params = parse_qs(parsed.query)
                    
                    current_offset = int(query_params.get('offset', ['0'])[0])
                    next_offset = current_offset + 42  # TradingView shows 42 strategies per page
                    
                    query_params['offset'] = [str(next_offset)]
                    new_query = urlencode(query_params, doseq=True)
                    next_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, 
                                         parsed.params, new_query, parsed.fragment))
                    
                    self.logger.info(f"Navigating to next page: {next_url}")
                    await page.goto(next_url, wait_until="networkidle")
                    return True
                else:
                    # Try adding offset parameter
                    separator = '&' if '?' in current_url else '?'
                    next_url = f"{current_url}{separator}offset=42"
                    self.logger.info(f"Trying with offset: {next_url}")
                    await page.goto(next_url, wait_until="networkidle")
                    return True
            
            if next_btn:
                # Check if button is disabled or hidden
                is_disabled = await next_btn.get_attribute("disabled")
                is_hidden = await next_btn.is_hidden()
                
                if is_disabled or is_hidden:
                    self.logger.info("Next button is disabled or hidden")
                    return False
                
                await next_btn.click()
                await page.wait_for_load_state("networkidle")
                return True
            
        except Exception as e:
            self.logger.warning(f"Failed to navigate to next page: {e}")
        
        return False


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Scrape TradingView strategies")
    parser.add_argument("--pages", type=int, help="Maximum pages to scrape")
    parser.add_argument("--editors-picks", action="store_true", 
                       help="Scrape editors' picks tab instead")
    parser.add_argument("--min-boosts", type=int, default=DEFAULT_MIN_BOOSTS,
                       help=f"Minimum boost count (default: {DEFAULT_MIN_BOOSTS})")
    parser.add_argument("--delay", type=float, default=DEFAULT_PAGE_DELAY,
                       help=f"Delay between pages in seconds (default: {DEFAULT_PAGE_DELAY})")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode (visible browser)")
    
    args = parser.parse_args()
    
    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)
    
    # Set debug mode
    if args.debug:
        BROWSER_LAUNCH_SETTINGS["headless"] = False
    
    scraper = TradingViewScraper(min_boosts=args.min_boosts, page_delay=args.delay)
    
    try:
        new_strategies = await scraper.scrape_strategies(
            max_pages=args.pages,
            editors_picks=args.editors_picks
        )
        
        # Load existing and merge
        existing_strategies = DataManager.load_strategies(STRATEGIES_FILE)
        existing_urls = {s.script_url for s in existing_strategies}
        
        # Only add truly new strategies
        unique_new = [s for s in new_strategies if s.script_url not in existing_urls]
        all_strategies = existing_strategies + unique_new
        
        # Save updated results
        DataManager.save_strategies(all_strategies, STRATEGIES_FILE)
        
        print(f"\n✅ Scraping completed!")
        print(f"📊 Total strategies in database: {len(all_strategies)}")
        print(f"🆕 New strategies added: {len(unique_new)}")
        print(f"💾 Saved to: {STRATEGIES_FILE}")
        
        if unique_new:
            print(f"\n🔥 Top new strategies by boost count:")
            sorted_new = sorted(unique_new, key=lambda x: x.boost_count, reverse=True)
            for strategy in sorted_new[:5]:
                print(f"  • {strategy.title} by {strategy.author} ({strategy.boost_count} boosts)")
    
    except KeyboardInterrupt:
        print("\n⚠️  Scraping interrupted by user")
    except Exception as e:
        print(f"\n❌ Scraping failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))