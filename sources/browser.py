"""
One page load in a visible Chromium window, for a site that refuses plain HTTP
clients and headless browsers alike.

A source calls browser.headed_get(url) and gets the final status and HTML; a
Playwright error propagates for the source to report. Needs a desktop display
and the browser from 'uv run playwright install chromium'.
"""
from playwright.async_api import async_playwright


async def headed_get(url: str, timeout_ms: int = 20000) -> tuple[int, str]:
    # -- leaving the context stops the driver, which closes the window on every path
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel="chromium", headless=False, timeout=timeout_ms)
        page = await browser.new_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        return response.status, await page.content()
