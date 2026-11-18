"""
CamelCamelCamel: Amazon price history (lowest, highest, average, current).

Gives the "is this a good price" verdict that Google Shopping cannot. Called by
the price-history tool with an ASIN taken from an Amazon URL. The site refuses
plain HTTP clients and headless browsers, so the product page is loaded once in
a visible Chromium window and never retried.
"""
import re

from bs4 import BeautifulSoup
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeout

from . import browser, http
from .envelope import envelope, skipped

ASIN = re.compile(r"^[A-Z0-9]{10}$")
ASIN_IN_URL = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?#]|$)")
LABELS = ("lowest", "highest", "average", "current")
DOLLARS = re.compile(r"\$\s*[\d,]+(?:\.\d+)?")


def asin_from_url(url_or_asin: str) -> str | None:
    if ASIN.match(url_or_asin):
        return url_or_asin
    m = ASIN_IN_URL.search(url_or_asin)
    return m.group(1) if m else None


def parse_ccc(html: str) -> dict | None:
    # -- Amazon's row of the price table, keyed by the first word of each header cell; a dash reads as None
    for table in BeautifulSoup(html, "html.parser").find_all("table"):
        rows = [[c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])] for r in table.find_all("tr")]
        amazon = next((r for r in rows if r and r[0].lower() == "amazon"), None)
        if amazon is None:
            continue
        prices = {}
        for head, cell in zip(rows[0], amazon):
            m = DOLLARS.search(cell)
            prices[head.lower().partition(" ")[0]] = http.money(m.group(0)) if m else None
        return {name: prices.get(name) for name in LABELS}
    return None


def verdict(hist: dict) -> str | None:
    current, lowest, average = hist["current"], hist["lowest"], hist["average"]
    # -- the tracker can hold a history with no live Amazon price; no verdict without one
    if current is None:
        return None
    if current <= lowest * 1.03:
        return "at/near all-time low"
    if current > average * 1.10:
        return "above average; consider waiting"
    if current < average:
        return "below average"
    return "around average"


async def get_price_history(asin: str | None) -> dict:
    if asin is None:
        return skipped("camelcamelcamel", "not_amazon")
    try:
        status, html = await browser.headed_get(f"https://camelcamelcamel.com/product/{asin}")
    except PlaywrightTimeout:
        return skipped("camelcamelcamel", "timeout")
    # -- a machine with no display or no Chromium install lands here as well
    except PlaywrightError:
        return skipped("camelcamelcamel", "blocked")
    if status in http.BLOCKED_STATUSES:
        return skipped("camelcamelcamel", "blocked")
    hist = parse_ccc(html)
    if hist is None or hist["lowest"] is None or hist["average"] is None:
        return skipped("camelcamelcamel", "no_results")
    return envelope({**hist, "verdict": verdict(hist)}, checked=["camelcamelcamel"])
