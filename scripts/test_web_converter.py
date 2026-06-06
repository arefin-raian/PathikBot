import asyncio, sys
sys.path.insert(0, '.')
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto('https://bangla.plus/bijoy-unicode-converter/', wait_until='load', timeout=30000)
        await page.wait_for_timeout(3000)
        
        test_text = 'মেসার্স আরেফিন ট্রেডার্স|\nমেসার্স আরেকটা কোম্পানি|'
        await page.fill('#uniText', '')
        await page.type('#uniText', test_text, delay=5)
        await page.click('#btnToBijoy')
        await page.wait_for_timeout(2000)
        
        result = await page.input_value('#bijoyText')
        
        # Save hex dump
        with open('C:\\Users\\Admin\\AppData\\Local\\Temp\\opencode\\hex_dump.txt', 'w', encoding='utf-8') as f:
            f.write(f'Length: {len(result)}\n')
            f.write(f'Repr: {repr(result)}\n')
            f.write(f'Chars:\n')
            for i, c in enumerate(result):
                f.write(f'  [{i}] U+{ord(c):04X} ({repr(c)})\n')
            f.write(f'\nSplit by newline:\n')
            for j, line in enumerate(result.split('\n')):
                f.write(f'  Line {j}: {repr(line)}\n')
                for i, c in enumerate(line):
                    f.write(f'    [{i}] U+{ord(c):04X}\n')

        await browser.close()
        print('Done - check hex_dump.txt')

asyncio.run(main())
