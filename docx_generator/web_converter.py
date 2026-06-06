from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

_DRIVER = None

CONVERTER_URL = "https://bangla.plus/bijoy-unicode-converter/"


def _ensure_driver():
    global _DRIVER
    if _DRIVER is None:
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        _DRIVER = webdriver.Chrome(options=opts)
        _DRIVER.get(CONVERTER_URL)
        WebDriverWait(_DRIVER, 20).until(
            EC.presence_of_element_located((By.ID, "btnToBijoy"))
        )
    return _DRIVER


def convert_unicode_to_bijoy(text: str) -> str:
    driver = _ensure_driver()
    unicode_input = driver.find_element(By.ID, "uniText")
    unicode_input.clear()
    unicode_input.send_keys(text)
    driver.find_element(By.ID, "btnToBijoy").click()
    WebDriverWait(driver, 10).until(
        lambda d: d.find_element(By.ID, "bijoyText").get_attribute("value") != ""
    )
    return driver.find_element(By.ID, "bijoyText").get_attribute("value")
