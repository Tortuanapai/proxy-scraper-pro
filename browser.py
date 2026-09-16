"""Conexion al navegador con Playwright (Chrome por defecto)."""
import random
from pathlib import Path

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]

def get_random_ua() -> str:
    return random.choice(USER_AGENTS)

BROWSER_CHANNELS = {
    "Chrome": {"channel": "chrome"},
    "Brave": {"channel": "brave"},
    "Edge": {"channel": "msedge"},
    "Firefox": {"channel": "firefox"},
}

def get_user_data_dir() -> str:
    base = Path.home() / ".proxy-scraper-profiles"
    base.mkdir(exist_ok=True)
    return str(base)

def launch_context(p, browser_name="Chrome", headless=False, use_profile=True):
    """Devuelve un BrowserContext sincrono de Playwright."""
    channel = BROWSER_CHANNELS.get(browser_name, {"channel": "chrome"})
    common = dict(
        headless=headless,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        user_agent=get_random_ua(),
        viewport={"width": 1366, "height": 768},
        ignore_https_errors=True,
    )
    if use_profile:
        return p.chromium.launch_persistent_context(get_user_data_dir(), **common, **channel)
    browser = p.chromium.launch(**common, **channel)
    return browser.new_context(user_agent=common["user_agent"])
