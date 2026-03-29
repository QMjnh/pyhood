#!/usr/bin/env python3
"""
Inspect TradingView page structure to understand current selectors.
"""

import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.append(str(Path(__file__).parent))
from config import STRATEGIES_URL, BROWSER_LAUNCH_SETTINGS, BROWSER_CONTEXT_SETTINGS

async def inspect_page():
    """Inspect the current page structure."""
    print("Inspecting TradingView page structure...")
    
    async with async_playwright() as p:
        # Launch browser in visible mode
        launch_settings = BROWSER_LAUNCH_SETTINGS.copy()
        launch_settings["headless"] = False
        
        browser = await p.chromium.launch(**launch_settings)
        context = await browser.new_context(**BROWSER_CONTEXT_SETTINGS)
        page = await context.new_page()
        
        try:
            print(f"Navigating to: {STRATEGIES_URL}")
            await page.goto(STRATEGIES_URL, wait_until="networkidle")
            await asyncio.sleep(5)
            
            # Get the main container HTML to understand structure
            print("Getting page structure...")
            
            # Find the main content area
            main_content = page.locator("main, .tv-feed, .content, [data-name='feed']").first
            if await main_content.count() > 0:
                html = await main_content.inner_html()
                print("Main content found, saving structure...")
                with open("page_structure.html", "w") as f:
                    f.write(html)
                print("✅ Saved page structure to page_structure.html")
            
            # Look for actual strategy cards by examining links
            script_links = page.locator("a[href*='/script/']")
            count = await script_links.count()
            print(f"\nFound {count} script links")
            
            if count > 0:
                print("Analyzing first 5 strategy links:")
                for i in range(min(5, count)):
                    link = script_links.nth(i)
                    href = await link.get_attribute("href")
                    text = await link.text_content()
                    
                    # Get the parent container
                    parent = link.locator("..")
                    parent_class = await parent.get_attribute("class")
                    
                    print(f"\nStrategy {i+1}:")
                    print(f"  Text: {text[:60]}")
                    print(f"  URL: {href}")
                    print(f"  Parent class: {parent_class}")
                    
                    # Look for boost/like counts near this link
                    container = parent
                    for level in range(3):  # Go up 3 levels
                        boost_patterns = [
                            "*[text()*='k' or text()*='boost' or text()*='like']",
                            "button *",
                            ".count, .number"
                        ]
                        
                        for pattern in boost_patterns:
                            try:
                                elements = container.locator(pattern)
                                elem_count = await elements.count()
                                if elem_count > 0:
                                    for j in range(min(3, elem_count)):
                                        elem_text = await elements.nth(j).text_content()
                                        if elem_text and any(c.isdigit() for c in elem_text):
                                            print(f"  Potential boost count: {elem_text}")
                            except:
                                pass
                        
                        container = container.locator("..")
                        if await container.count() == 0:
                            break
            
            print("\n🔍 Browser will stay open for 30 seconds for manual inspection...")
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"❌ Error during inspection: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    try:
        asyncio.run(inspect_page())
    except KeyboardInterrupt:
        print("\n⚠️ Inspection interrupted by user")