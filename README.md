# shopping-research

A local MCP server that gives Claude Code live product search, cross-retailer prices, Amazon price history, community deals, and an optional Capital One Shopping cross-check, over free sources only. Every tool reports its own coverage: the response envelope is `{data, sources_checked, sources_skipped}`, so the calling skill can never claim a best price over a source it never saw.

## Install as a plugin

Requires [uv](https://docs.astral.sh/uv/) on your PATH; the server runs under `uv run` and creates its own environment on first start.

```
/plugin install shopping-research --marketplace tannerorourke/shopping-research-mcp
```

Claude Code prompts for the API keys when the plugin is enabled (SerpApi, eBay client ID and secret); each is optional and a blank one leaves that source registered and reported as `disabled_in_settings`. Edit them later under `/plugin`, Installed, Configure options. The SerpApi monthly budget and the Target toggle are options there too. Anything else from `settings.toml.example` (the C1 cross-check, cache TTL) goes in `settings.toml` inside the plugin's data directory, `~/.claude/plugins/data/<plugin id>/`, where the server also keeps its SerpApi counter and eBay token. `uv run playwright install chromium` inside the installed plugin directory enables price history and the headless-browser fallback.

The skill arrives as `/shopping-research:shopping-research`.

## Run from a clone

1. `uv sync` installs the environment (Python 3.12 or newer).
2. `cp settings.toml.example settings.toml` and fill the keys you have. Each key can also come from the environment variable named in the file. A blank key leaves that source registered and reported as `disabled_in_settings`.
3. `uv run playwright install chromium` enables `get_price_history`, the headless-browser fallback in `extract_product`, and the optional `c1_check`.
4. Register the server. Project scope: the shipped `.mcp.json` runs `uv run server.py` from this directory. User scope, so the tools are available from any directory:

```bash
claude mcp add --scope user shopping-research -- uv run --directory /absolute/path/to/shopping-research server.py
```

5. Copy or symlink `skills/shopping-research/` into `~/.claude/skills/` to make the skill available outside this repository.

Pass condition: `get_status` from a Claude Code session returns `serpapi_remaining` and the configured flags.

## Sources

| Source | Provides | Free tier | Key |
| --- | --- | --- | --- |
| SerpApi `google_shopping` / `google_product` | cross-retailer search and per-merchant offers | 250 searches a month | `SERPAPI_KEY` |
| eBay Browse API | marketplace listings | 5,000 calls a day | `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` |
| Target RedSky | price, availability | undocumented public key, off by default | none |
| Shopify `/products/<handle>.json`, schema.org JSON-LD, OpenGraph, Playwright | any product page | none | none |
| CamelCamelCamel | Amazon price history | one page load in a visible browser window | none |
| Slickdeals RSS | community deals (US) | hourly feed | none |
| Capital One Shopping extension via Playwright | coupon-adjusted cross-check on finalists | free account, off by default | sign in once in the profile |

The SerpApi monthly counter and cache persist in `~/.best-price/` (override with `BEST_PRICE_STATE`). The server refuses SerpApi calls past `monthly_budget`.

Target is off by default, since its endpoint refuses most automated requests, and every search reports it as `disabled_in_settings`. Turn it on with `[target] enabled = true` in `settings.toml`, `TARGET_ENABLED=true`, or the plugin's Query Target option.

## Tools

`search_products`, `compare_prices`, `get_condition`, `extract_product`, `get_price_history`, `get_deals`, `c1_check`, `get_status`, `reload_settings`. Signatures and the skip-reason vocabulary are documented in `skills/shopping-research/SKILL.md`; the vocabulary itself is `sources/envelope.py`.

## Enabling the C1 cross-check

1. Unpack the Capital One Shopping extension into `extensions/c1shopping-unpacked/` (an unpacked directory, never a `.crx`).
2. Set `[c1] enabled = true` and `headless = false` in `settings.toml`, run `reload_settings`, call `c1_check` on an Amazon product URL, and sign in when the extension asks.
3. In `chrome://extensions`, open the extension's service worker and read the price-comparison endpoint from its Network tab. Write a unique substring of it into `api_url_filter`.
4. Set `headless = true` and `reload_settings`. `c1/parsers.py` is written against the common payload shapes; adjust it once if the endpoint's shape differs.

## Sources and their terms

SerpApi, eBay, and Slickdeals RSS are used through their published interfaces. Target's search endpoint is undocumented, gets one request per call, and is off by default. CamelCamelCamel refuses plain HTTP clients and headless browsers, so its product page is loaded once per call in a visible Chromium window on your desktop, with no stealth patch and no retry; a machine with no display reports `blocked`. A refusal from either site is reported as `blocked` and never retried. The Capital One Shopping cross-check drives a browser extension in your own signed-in profile and is off by default. Use each source within its terms.
