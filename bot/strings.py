import json
import os

_strings = None

def _load():
    global _strings
    path = os.path.join(os.path.dirname(__file__), 'strings.json')
    with open(path, 'r', encoding='utf-8') as f:
        _strings = json.load(f)

def S(key, **kwargs):
    """Get a localized string by dot-separated key with optional format args."""
    if _strings is None:
        _load()
    keys = key.split('.')
    val = _strings
    for k in keys:
        val = val[k]
    if kwargs:
        return val.format(**kwargs)
    return val

def bot_commands():
    """Return list of BotCommand tuples from strings.json."""
    if _strings is None:
        _load()
    cmds = []
    for cmd, desc in _strings['bot_commands'].items():
        from telegram import BotCommand
        cmds.append(BotCommand(cmd, desc))
    return cmds
