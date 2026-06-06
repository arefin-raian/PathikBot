import json
import urllib.request
import urllib.error

API_URL = "https://bijoy.converteraz.com/api/convert/unicode-to-bijoy"


def convert_unicode_to_bijoy(text: str) -> str:
    data = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=data, headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=15)
    result = json.loads(resp.read())
    return result["output"]
