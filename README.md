# shopping-research

A local MCP server that gives Claude Code live product search, cross-retailer prices, Amazon price history, community deals, and an optional Capital One Shopping cross-check, over free sources only. Every tool reports its own coverage: the response envelope is `{data, sources_checked, sources_skipped}`, so the calling skill can never claim a best price over a source it never saw.

## Install as a plugin

Requires [uv](https://docs.astral.sh/uv/) on your PATH; the server runs under `uv run` and creates its own environment on first start.

Add the `tannerorourke` plugin index once, then install from it:

```bash
claude plugin marketplace add tannerorourke/plugins
claude plugin install shopping-research@tannerorourke
```

Claude Code prompts for the API keys when the plugin is enabled (SerpApi, eBay client ID and secret); each is optional and a blank one leaves that source registered and reported as `disabled_in_settings`. Edit them later under `/plugin`, Installed, Configure options. The SerpApi monthly budget and the Target toggle are options there too. Anything else from `settings.toml.example` (the C1 cross-check, cache TTL) goes in `settings.toml` inside the plugin's data directory, `~/.claude/plugins/data/<plugin id>/`, where the server also keeps its SerpApi counter and eBay token. `uv run playwright install chromium` inside the installed plugin directory enables price history and the headless-browser fallback.

The skill arrives as `/shopping-research:shopping-research`.

## Install in the Claude Desktop app

The desktop bundle is one file, `shopping-research.mcpb`. It runs the same server on your own machine, and the app's Settings screen takes the keys.

1. Install [uv](https://docs.astral.sh/uv/) and check that `uv --version` answers in a new terminal. The app starts the server with `uv run`, which fetches Python and the dependencies on the first start.
2. Build the bundle from a clone with `npx @anthropic-ai/mcpb pack . shopping-research.mcpb`. The pack leaves out `settings.toml`, the tests, and the environment.
3. Double-click the file, or drag it onto Settings, Extensions in the app.
4. Fill the options the app shows: the SerpApi key, the eBay client ID and secret, the monthly budget, and the Target toggle. Each is optional, and a blank key leaves that source reported as `disabled_in_settings`.
5. Run `uv run playwright install chromium` once from a clone at the same version. The browser lands in a per-user folder the installed server shares, and it enables `get_price_history` and the headless-browser fallback. Without it, price history reports `blocked`.

The counter, the eBay token, and an optional `settings.toml` for the C1 cross-check and the cache TTL live in `~/.best-price/`, outside the bundle, so an update keeps them.

The bundle carries the server only. Upload `skills/shopping-research/` as a skill in the app to get the workflow and the `Not checked:` report.

Pass condition: `get_status` in a new chat returns `serpapi_configured: true` once the key is entered.

If the install dialog reports a `uv` error about a file in use, look under Settings, Extensions before retrying. The extension can be listed anyway, and its first start finishes building the environment.

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
