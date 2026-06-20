"""
Unicode → Bijoy converter.

Primary: REST API at https://bijoy.converteraz.com (fast, no browser needed).
Fallback: headless Chromium via Playwright driving bangla.plus when the API
          is unreachable, rate-limited, or returns an unexpected payload.

The fallback preserves the previously-working browser flow so distributor
names and other Bangla text keep converting correctly even if the API is
down.
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

API_URL = "https://bijoy.converteraz.com/api/convert/unicode-to-bijoy"
API_TIMEOUT = 10  # seconds

CONVERTER_URL = "https://bangla.plus/bijoy-unicode-converter/"

_BROWSER = None


# ---------------------------------------------------------------------------
# Primary: REST API
# ---------------------------------------------------------------------------
def _convert_via_api(text: str) -> str:
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "PathikBot/1.0 (+https://github.com/arefin-raian/PathikBot)",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
        body = resp.read().decode("utf-8")
    data = json.loads(body)
    if not data.get("success") or "output" not in data:
        raise RuntimeError(f"Unexpected API payload: {body[:200]}")
    return data["output"]


# ---------------------------------------------------------------------------
# Fallback: headless browser driving bangla.plus
# ---------------------------------------------------------------------------
def _get_browser():
    global _BROWSER
    if _BROWSER is None:
        from playwright.sync_api import sync_playwright
        _BROWSER = sync_playwright().start().chromium.launch(headless=True)
    return _BROWSER


def _convert_via_browser(text: str) -> str:
    browser = _get_browser()
    page = browser.new_page()
    try:
        page.goto(CONVERTER_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector("#btnToBijoy", timeout=15000)
        page.fill("#uniText", "")
        page.type("#uniText", text, delay=5)
        page.click("#btnToBijoy")
        page.wait_for_timeout(2000)
        return page.input_value("#bijoyText")
    finally:
        page.close()


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def convert_unicode_to_bijoy(text: str) -> str:
    if not text:
        return text
    try:
        return _convert_via_api(text)
    except Exception as api_err:  # noqa: BLE001
        logger.warning(
            "Bijoy API failed (%s); falling back to browser converter.",
            api_err,
        )
        try:
            return _convert_via_browser(text)
        except Exception as browser_err:  # noqa: BLE001
            logger.error(
                "Browser fallback also failed: %s. Returning original text.",
                browser_err,
            )
            raise
