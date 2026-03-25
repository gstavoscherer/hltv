"""Shared Selenium helpers: driver creation, rate limiting, concurrency control."""

from __future__ import annotations

import logging
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time

import undetected_chromedriver as uc

logger = logging.getLogger(__name__)

_MAX = int(os.getenv("SELENIUM_MAX_CONCURRENCY", "1"))
_SEMAPHORE = threading.Semaphore(_MAX)


def acquire_slot():
    _SEMAPHORE.acquire()


def release_slot():
    _SEMAPHORE.release()


def wrap_quit(driver):
    released = {"done": False}
    original_quit = driver.quit

    def quit_with_release():
        try:
            original_quit()
        finally:
            if not released["done"]:
                released["done"] = True
                _SEMAPHORE.release()

    driver.quit = quit_with_release
    return driver


def _resolve_chrome_binary():
    """Return a Chrome/Chromium binary path if one exists on this host."""
    env_path = os.getenv("CHROME_BINARY")
    if env_path and os.path.exists(env_path):
        return env_path

    candidates = []
    if sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        ]
    elif sys.platform.startswith("linux"):
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]
    elif sys.platform.startswith("win"):
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        ]

    for path in candidates:
        if path and os.path.exists(path):
            return path

    for name in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]:
        path = shutil.which(name)
        if path:
            return path

    return None


def _detect_chrome_version():
    """Detect installed Chrome major version."""
    binary = _resolve_chrome_binary()
    if not binary:
        return None
    try:
        out = subprocess.check_output([binary, "--version"], stderr=subprocess.DEVNULL, timeout=5)
        match = re.search(r'(\d+)\.', out.decode())
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None


def wait_for_cloudflare(driver, timeout=15):
    """Wait for Cloudflare challenge to resolve if present."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            title = (driver.title or "").lower()
            page = (driver.page_source or "")[:500].lower()
        except Exception:
            # Window may have closed during redirect
            time.sleep(2)
            continue

        if "just a moment" in title or "attention required" in title:
            time.sleep(2)
            continue
        if "cloudflare" in page and "challenge" in page:
            time.sleep(2)
            continue

        return True

    logger.warning("Cloudflare challenge did not resolve within %ds", timeout)
    return False


def random_delay(min_s=1.0, max_s=3.0):
    """Sleep for a random duration to appear more human."""
    time.sleep(random.uniform(min_s, max_s))


def _make_options():
    """Create a fresh ChromeOptions."""
    options = uc.ChromeOptions()

    binary = _resolve_chrome_binary()
    if binary:
        options.binary_location = binary

    # Essential options for VPS environments
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--window-size=1920,1080')

    return options


def create_driver(headless=True):
    """Create undetected Chrome driver with Cloudflare bypass.

    For VPS without display, install xvfb and run with:
        xvfb-run python3 sync_all.py

    This gives Chrome a virtual display so it runs non-headless
    (which bypasses Cloudflare) without needing a real screen.
    """
    acquire_slot()

    version = _detect_chrome_version()

    # On VPS: use xvfb-run instead of headless for best Cloudflare bypass.
    # headless=False with xvfb is the most reliable approach.
    # headless=True is a fallback that may get blocked by Cloudflare.

    last_error = None
    for attempt in range(1, 4):
        try:
            options = _make_options()
            driver = uc.Chrome(
                options=options,
                use_subprocess=True,
                version_main=version,
                headless=headless,
            )
            break
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 2)
            else:
                release_slot()
                raise last_error

    driver = wrap_quit(driver)
    return driver
