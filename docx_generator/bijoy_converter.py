import sys
import os
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)
from converter import Unicode

_converter = Unicode()

def convert_to_bijoy(text):
    return _converter.convertUnicodeToBijoy(text)
