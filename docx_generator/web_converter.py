import asyncio
from playwright.async_api import async_playwright

_BROWSER = None
_PAGE = None

CONVERTER_URL = "https://bangla.plus/bijoy-unicode-converter/"


async def _ensure_page():
    global _BROWSER, _PAGE
    if _PAGE is None:
        p = await async_playwright().start()
        _BROWSER = await p.chromium.launch(headless=True)
        _PAGE = await _BROWSER.new_page()
        await _PAGE.goto(CONVERTER_URL, wait_until="domcontentloaded", timeout=30000)
        await _PAGE.wait_for_selector("#btnToBijoy", timeout=15000)
        await _PAGE.wait_for_timeout(1000)
    return _PAGE


async def _convert_text(text: str) -> str:
    page = await _ensure_page()
    await page.fill("#uniText", "")
    await page.type("#uniText", text, delay=5)
    await page.click("#btnToBijoy")
    await page.wait_for_timeout(1500)
    return await page.input_value("#bijoyText")


def convert_unicode_to_bijoy(text: str) -> str:
    return asyncio.run(_convert_text(text))


async def cleanup():
    global _BROWSER, _PAGE
    if _PAGE:
        await _PAGE.close()
        _PAGE = None
    if _BROWSER:
        await _BROWSER.stop()
        _BROWSER = None
