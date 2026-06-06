import asyncio
import threading
from playwright.async_api import async_playwright

_BROWSER = None
_PAGE = None
_LOCK = threading.Lock()
_LOOP = None
_THREAD = None

CONVERTER_URL = "https://bangla.plus/bijoy-unicode-converter/"


def _start_loop():
    global _LOOP, _THREAD
    _LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(_LOOP)
    _LOOP.run_forever()


def _get_loop():
    global _LOOP, _THREAD
    if _LOOP is None:
        _THREAD = threading.Thread(target=_start_loop, daemon=True)
        _THREAD.start()
        # Wait for loop to be ready
        while _LOOP is None:
            pass
    return _LOOP


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
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(_convert_text(text), loop)
    return future.result()
