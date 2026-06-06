from playwright.sync_api import sync_playwright

_BROWSER = None

CONVERTER_URL = "https://bangla.plus/bijoy-unicode-converter/"


def _get_browser():
    global _BROWSER
    if _BROWSER is None:
        _BROWSER = sync_playwright().start().chromium.launch(
            headless=True, channel="chrome"
        )
    return _BROWSER


def convert_unicode_to_bijoy(text: str) -> str:
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
