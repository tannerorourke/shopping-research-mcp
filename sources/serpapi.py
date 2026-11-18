"""
SerpApi: Google Shopping search and per-merchant offers (google_product engine).

Primary discovery and comparison source. Every call passes through
'serpapi_budget', so a month past 'monthly_budget' returns 'quota_exhausted'
instead of a request, and a repeated query is served from the cache.
"""
from urllib.parse import urljoin

import httpx

from . import http
from .budget import serpapi_budget
from .envelope import envelope, skipped

SEARCH_URL = "https://serpapi.com/search"
GOOGLE = "https://www.google.com"
PUBLIC = ("title", "price", "merchant", "url", "product_id")


async def _call(params: dict) -> tuple[dict | None, str | None]:
    """Returns (json, None) on success, (None, skip_reason) otherwise. Spends budget only on 200."""
    try:
        async with http.client() as c:
            r = await c.get(SEARCH_URL, params={**params, "api_key": serpapi_budget.key})
    except httpx.TimeoutException:
        return None, "timeout"
    if r.status_code == 401:
        return None, "auth_error"
    if r.status_code != 200:
        return None, "blocked"
    serpapi_budget.spend()
    return r.json(), None


async def search_products(query: str, num: int = 10) -> dict:
    # -- the engine returns a full page whatever 'num' asks, so one cached page serves every 'num'
    cache_key = ("page", query)
    cached = serpapi_budget.cache_get(cache_key)
    if cached:
        return envelope(_public(cached, num), checked=["serpapi:cache"])
    if not serpapi_budget.key:
        return skipped("serpapi", "disabled_in_settings", data=[])
    if not serpapi_budget.can_spend():
        return skipped("serpapi", "quota_exhausted", data=[])
    body, reason = await _call({"engine": "google_shopping", "q": query, "num": num})
    if reason:
        return skipped("serpapi", reason, data=[])
    items = [{
        "title": i.get("title"),
        "price": i.get("extracted_price"),
        "merchant": i.get("source"),
        "url": i.get("product_link") or i.get("link"),
        "product_id": i.get("product_id"),
        "condition": i.get("second_hand_condition") or "new",
    } for i in body.get("shopping_results", [])]
    # -- an empty answer is never cached: the next call may find the product listed
    if not items:
        return skipped("serpapi", "no_results", data=[])
    serpapi_budget.cache_put(cache_key, items)
    return envelope(_public(items, num), checked=["serpapi"])


def _public(page: list[dict], num: int) -> list[dict]:
    # -- 'condition' stays in the cached page for condition_of; a search item keeps its five fields
    return [{k: item[k] for k in PUBLIC} for item in page[:num]]


def condition_of(product_id: str) -> dict:
    # -- one catalog product can sit behind several listings, so every match is returned, deduplicated
    matches = {(i["merchant"], i["price"], i["condition"]): i
               for page in serpapi_budget.cache_scan("page") for i in page if i["product_id"] == product_id}
    if not matches:
        return skipped("serpapi:cache", "no_results", data=[])
    return envelope([{k: i[k] for k in ("condition", "merchant", "price", "title")} for i in matches.values()],
                    checked=["serpapi:cache"])


async def compare_prices(product_id: str | None = None, query: str | None = None) -> dict:
    if product_id is None:
        hits = await search_products(query, num=1)
        if not hits["data"] or not hits["data"][0].get("product_id"):
            return envelope([], checked=hits["sources_checked"],
                            skipped=hits["sources_skipped"] or [{"name": "serpapi", "reason": "no_results"}])
        product_id = hits["data"][0]["product_id"]
    cache_key = ("product", product_id)
    cached = serpapi_budget.cache_get(cache_key)
    if cached:
        return envelope(cached, checked=["serpapi:google_product:cache"])
    if not serpapi_budget.key:
        return skipped("serpapi", "disabled_in_settings", data=[])
    if not serpapi_budget.can_spend():
        return skipped("serpapi", "quota_exhausted", data=[])
    body, reason = await _call({"engine": "google_product", "product_id": product_id, "offers": "1"})
    if reason:
        return skipped("serpapi", reason, data=[])
    stores = body.get("product_results", {}).get("stores", [])
    # -- a store link can arrive as a Google redirect path ('/goto?url=...'); resolve it against google.com
    offers = sorted(
        [{"merchant": s.get("name"), "price": s.get("extracted_price"), "total_price": s.get("extracted_total"),
          "url": urljoin(GOOGLE, s["link"]) if s.get("link") else None} for s in stores],
        key=lambda o: o["price"] if o["price"] is not None else 1e9)
    if not offers:
        return skipped("serpapi:google_product", "no_results", data=[])
    serpapi_budget.cache_put(cache_key, offers)
    return envelope(offers, checked=["serpapi:google_product"])
