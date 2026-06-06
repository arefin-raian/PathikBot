import asyncio, sys
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://bangla.plus/bijoy-unicode-converter/', wait_until='load', timeout=30000)
        await page.wait_for_timeout(3000)
        elements = await page.query_selector_all('textarea, button, input[type]:not([type=hidden]), select')
        print(f"Found {len(elements)} elements:", flush=True)
        for el in elements:
            tag = await el.evaluate('e => e.tagName')
            type_attr = await el.get_attribute('type') or ''
            id_attr = await el.get_attribute('id') or ''
            class_attr = await el.get_attribute('class') or ''
            placeholder = await el.get_attribute('placeholder') or ''
            name_attr = await el.get_attribute('name') or ''
            # Print as repr to avoid encoding issues
            line = f'  {tag} type={type_attr!r} id={id_attr!r} name={name_attr!r} class={class_attr[:60]!r} placeholder={placeholder!r}'
            print(line.encode('ascii', 'replace').decode(), flush=True)
        
        title = await page.title()
        print(f"Page title: {title!r}", flush=True)
        await browser.close()

asyncio.run(inspect())
