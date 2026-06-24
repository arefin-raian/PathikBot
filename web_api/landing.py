"""Public landing page + uptime endpoints for PathikBot.

Render's free tier spins a service down after ~15 min of inactivity and a cold
start takes ~50s. To stay warm we expose:

  GET /        -> a terminal-styled HTML status page (200) for humans
  GET /ping    -> tiny text/plain "pong" (200) for uptime monitors
  GET /status  -> JSON uptime payload (200) for keyword-based monitors

Every one of these returns HTTP 200 so UptimeRobot (or any HTTP/keyword
monitor) registers the service as UP and keeps pinging it awake. Point your
monitor at the bare onrender.com URL (which now hits `/`) or at `/ping`.
"""
from __future__ import annotations

import os
import time

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

router = APIRouter()

# Captured once at import (process boot). Used to report uptime.
_BOOT_TS = time.time()

# Raw ASCII banner. Kept as a separate constant so the f-string template below
# stays readable and the backslashes don't need doubling inside HTML.
_BANNER = r"""
  ____       _   _     _ _    ____        _
 |  _ \ __ _| |_| |__ (_) | _| __ )  ___ | |_
 | |_) / _` | __| '_ \| | |/ /  _ \ / _ \| __|
 |  __/ (_| | |_| | | | |   <| |_) | (_) | |_
 |_|   \__,_|\__|_| |_|_|_|\_\____/ \___/ \__|
"""


def _fmt_uptime(seconds: float) -> str:
    """Human readable d/h/m/s uptime string."""
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if mins or hours or days:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def _uptime_payload() -> dict:
    now = time.time()
    return {
        "service": "PathikBot",
        "status": "online",
        "ok": True,
        "uptime_seconds": round(now - _BOOT_TS, 1),
        "uptime_human": _fmt_uptime(now - _BOOT_TS),
        "bot_enabled": os.getenv("DISABLE_BOT") != "1",
    }


@router.get("/ping", response_class=PlainTextResponse)
async def ping() -> str:
    """Bare-minimum keep-alive endpoint for uptime monitors."""
    return "pong"


@router.get("/status")
async def status() -> JSONResponse:
    """JSON uptime payload. Monitor on keyword `online` if you like."""
    return JSONResponse(_uptime_payload())


@router.get("/", response_class=HTMLResponse)
async def landing() -> str:
    """Terminal-styled status page served at the service root (HTTP 200)."""
    data = _uptime_payload()
    bot_state = "ONLINE" if data["bot_enabled"] else "DISABLED"
    return _PAGE.format(
        banner=_BANNER,
        uptime=data["uptime_human"],
        bot_state=bot_state,
    )


# --------------------------------------------------------------------------- #
# HTML template. Self-contained (no external assets) so it loads instantly and
# survives a cold start. Styled like a hacker terminal: scanlines, green CRT
# glow, blinking cursor, boot-sequence typewriter log.
# --------------------------------------------------------------------------- #
_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PathikBot :: status</title>
<style>
  :root {{ --grn:#39ff14; --dim:#1f8a12; --bg:#040d04; }}
  * {{ box-sizing:border-box; }}
  html,body {{ margin:0; height:100%; background:var(--bg); }}
  body {{
    font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
    color:var(--grn); display:flex; align-items:center; justify-content:center;
    min-height:100vh; padding:24px; overflow-x:hidden;
    text-shadow:0 0 4px rgba(57,255,20,.55);
  }}
  /* CRT scanline overlay */
  body::after {{
    content:""; position:fixed; inset:0; pointer-events:none; z-index:9;
    background:repeating-linear-gradient(0deg,
      rgba(0,0,0,0) 0px, rgba(0,0,0,0) 2px,
      rgba(0,0,0,.18) 3px, rgba(0,0,0,.18) 3px);
    animation:flicker 3.5s infinite;
  }}
  @keyframes flicker {{ 0%,100%{{opacity:.92}} 50%{{opacity:1}} }}
  .term {{
    width:100%; max-width:760px; background:rgba(2,8,2,.85);
    border:1px solid var(--dim); border-radius:8px;
    box-shadow:0 0 24px rgba(57,255,20,.25), inset 0 0 60px rgba(57,255,20,.05);
    overflow:hidden;
  }}
  .bar {{
    display:flex; align-items:center; gap:8px; padding:8px 12px;
    background:#0a1a0a; border-bottom:1px solid var(--dim);
  }}
  .dot {{ width:12px; height:12px; border-radius:50%; }}
  .r{{background:#ff5f56}} .y{{background:#ffbd2e}} .g{{background:#27c93f}}
  .bar .t {{ margin-left:8px; color:var(--dim); font-size:13px; }}
  .body {{ padding:18px 22px 26px; font-size:14px; line-height:1.5; }}
  pre.banner {{
    color:var(--grn); margin:0 0 14px; font-size:12px; line-height:1.15;
    white-space:pre; overflow-x:auto;
  }}
  .log p {{ margin:2px 0; opacity:0; animation:type .35s steps(1) forwards; }}
  .log p:nth-child(1){{animation-delay:.15s}}
  .log p:nth-child(2){{animation-delay:.45s}}
  .log p:nth-child(3){{animation-delay:.75s}}
  .log p:nth-child(4){{animation-delay:1.05s}}
  .log p:nth-child(5){{animation-delay:1.35s}}
  .log p:nth-child(6){{animation-delay:1.65s}}
  .log p:nth-child(7){{animation-delay:1.95s}}
  @keyframes type {{ to {{opacity:1}} }}
  .ok {{ color:var(--grn); }}
  .key {{ color:#7fff6a; }}
  .muted {{ color:var(--dim); }}
  .pulse {{
    display:inline-block; width:9px; height:9px; border-radius:50%;
    background:var(--grn); box-shadow:0 0 8px var(--grn);
    animation:pulse 1.2s infinite; vertical-align:middle; margin-right:6px;
  }}
  @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.25}} }}
  .cursor {{
    display:inline-block; width:9px; height:16px; background:var(--grn);
    margin-left:4px; vertical-align:text-bottom; animation:blink 1s step-end infinite;
  }}
  @keyframes blink {{ 50%{{opacity:0}} }}
  a {{ color:#7fff6a; }}
</style>
</head>
<body>
  <div class="term">
    <div class="bar">
      <span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
      <span class="t">root@pathikbot:~ — secure shell</span>
    </div>
    <div class="body">
      <pre class="banner">{banner}</pre>
      <div class="log">
        <p><span class="muted">$</span> ./pathikbot --status</p>
        <p><span class="ok">[ OK ]</span> Telegram polling loop ......... <span class="key">{bot_state}</span></p>
        <p><span class="ok">[ OK ]</span> FastAPI service ............... <span class="key">LISTENING</span></p>
        <p><span class="ok">[ OK ]</span> MongoDB datastore ............. <span class="key">LINKED</span></p>
        <p><span class="ok">[ OK ]</span> Logsheet engine (DOCX/PDF/ODT)  <span class="key">ARMED</span></p>
        <p class="muted">uptime: {uptime} &nbsp;|&nbsp; node: render.com (free)</p>
        <p><span class="pulse"></span>system nominal — keep-alive at <span class="key">/ping</span><span class="cursor"></span></p>
      </div>
      <p class="muted" style="margin-top:18px;font-size:12px">
        PathikBot &mdash; Telegram-driven daily logsheet &amp; expense automation.
        Generates field-officer report sheets and crunches expenses on demand.<br>
        endpoints: <a href="/ping">/ping</a> &middot; <a href="/status">/status</a> &middot; <a href="/api/health">/api/health</a>
      </p>
    </div>
  </div>
</body>
</html>"""
