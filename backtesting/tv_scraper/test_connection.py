#!/usr/bin/env python3
"""
Quick test to verify TradingView access and page structure.
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.append(str(Path(__file__).parent))
from config import STRATEGIES_URL, BROWSER_LAUNCH_SETTINGS, BROWSER_CONTEXT_SETTINGS

async def test_connection():
    """Test basic connection to TradingView and inspect page structure."""
    print("Testing TradingView connection...")
    
    async with async_playwright() as p:
        # Launch browser in visible mode for testing
        launch_settings = BROWSER_LAUNCH_SETTINGS.copy()
        launch_settings["headless"] = False
        
        browser = await p.chromium.launch(**launch_settings)
        context = await browser.new_context(**BROWSER_CONTEXT_SETTINGS)
        page = await context.new_page()
        
        try:
            print(f"Navigating to: {STRATEGIES_URL}")
            await page.goto(STRATEGIES_URL, wait_until="networkidle")
            
            print("✅ Page loaded successfully")
            print(f"Current URL: {page.url}")
            print(f"Page title: {await page.title()}")
            
            # Wait for content to load
            await asyncio.sleep(5)
            
            # Check for common elements
            print("\nLooking for strategy containers...")
            
            # Test different selectors
            selectors_to_test = [
                ".tv-script-container",
                "[data-name='script-card']", 
                ".script-item",
                ".idea-card",
                ".tv-widget-idea",
                ".tv-feed-container",
                ".js-userlink-popup-anchor"
            ]
            
            found_selectors = []
            for selector in selectors_to_test:
                elements = page.locator(selector)
                count = await elements.count()
                if count > 0:
                    found_selectors.append((selector, count))
                    print(f"  ✅ Found {count} elements with selector: {selector}")
                else:
                    print(f"  ❌ No elements found for selector: {selector}")
            
            # If we found any containers, let's look at their structure
            if found_selectors:
                print(f"\nInspecting first container with selector: {found_selectors[0][0]}")
                first_container = page.locator(found_selectors[0][0]).first
                
                # Get all links in the container
                links = first_container.locator("a")
                link_count = await links.count()
                print(f"Found {link_count} links in first container")
                
                for i in range(min(3, link_count)):  # Check first 3 links
                    link = links.nth(i)
                    href = await link.get_attribute("href")
                    text = await link.text_content()
                    print(f"  Link {i+1}: {text[:50]}{'...' if len(text or '') > 50 else ''} -> {href}")
            
            # Check for pagination
            print(f"\nLooking for pagination...")
            pagination_selectors = [
                ".tv-feed__pagination",
                ".paginator", 
                ".pagination",
                "[data-name='pagination']"
            ]
            
            for selector in pagination_selectors:
                elements = page.locator(selector)
                count = await elements.count()
                if count > 0:
                    print(f"  ✅ Found pagination with selector: {selector}")
                    text = await elements.first.text_content()
                    print(f"  Pagination text: {text[:100] if text else 'No text'}")
                else:
                    print(f"  ❌ No pagination found for selector: {selector}")
            
            print("\n🔍 Waiting 10 seconds for you to inspect the page...")
            print("Press Ctrl+C to exit early")
            await asyncio.sleep(10)
            
        except Exception as e:
            print(f"❌ Error during testing: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(test_connection())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")