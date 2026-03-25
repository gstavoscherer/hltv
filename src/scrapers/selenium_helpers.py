"""Shared Selenium helpers: driver creation, rate limiting, concurrency control."""

from __future__ import annotations

import logging
import os
import queue
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


_DRIVER_LOCK = threading.Lock()
_PATCHER_READY = False


def _ensure_chromedriver():
    """Pre-patch chromedriver once with the correct version.

    undetected-chromedriver's Patcher can download the wrong version
    when called concurrently or repeatedly. We call it once upfront
    and let subsequent uc.Chrome calls reuse the patched binary.
    """
    global _PATCHER_READY
    if _PATCHER_READY:
        return
    version = _detect_chrome_version()
    patcher = uc.Patcher(version_main=version) if version else uc.Patcher()
    patcher.auto()
    _PATCHER_READY = True
    logger.info("Chromedriver patched: %s", getattr(patcher, 'version_full', '?'))


def _create_driver_raw(headless=True):
    """Create a Chrome driver without acquiring a semaphore slot.

    Used internally by DriverPool which manages its own concurrency.
    A lock serializes creation to prevent undetected-chromedriver from
    patching the shared binary concurrently (which causes version mismatches).
    """
    version = _detect_chrome_version()

    last_error = None
    for attempt in range(1, 4):
        try:
            with _DRIVER_LOCK:
                _ensure_chromedriver()
                options = _make_options()
                kwargs = dict(
                    options=options,
                    use_subprocess=True,
                    headless=headless,
                )
                if version:
                    kwargs['version_main'] = version
                driver = uc.Chrome(**kwargs)
            return driver
        except Exception as exc:
            last_error = exc
            logger.warning("_create_driver_raw attempt %d failed: %s", attempt, exc)
            if attempt < 3:
                time.sleep(attempt * 3)
    raise last_error


def create_driver(headless=True):
    """Create undetected Chrome driver with Cloudflare bypass.

    For VPS without display, install xvfb and run with:
        xvfb-run python3 sync_all.py

    This gives Chrome a virtual display so it runs non-headless
    (which bypasses Cloudflare) without needing a real screen.
    """
    _ensure_chromedriver()
    acquire_slot()

    version = _detect_chrome_version()

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


class DriverPool:
    """Pool of reusable Chrome drivers for faster batch scraping.

    Drivers are warmed up (Cloudflare cookie resolved) on first use,
    then reused for subsequent requests — skipping the challenge overhead.

    Usage:
        with DriverPool(size=3, headless=False) as pool:
            driver = pool.checkout()
            try:
                driver.get(url)
                ...
            except Exception:
                pool.mark_bad(driver)  # will be replaced
            finally:
                pool.checkin(driver)
    """

    def __init__(self, size=3, headless=True):
        self._size = size
        self._headless = headless
        self._queue: queue.Queue = queue.Queue()
        self._drivers: list = []
        self._bad: set = set()
        self._lock = threading.Lock()
        self._closed = False

    def start(self):
        """Create all drivers sequentially and warm them up.

        undetected-chromedriver patches a shared binary, so drivers must be
        created one at a time to avoid version conflicts.
        """
        for i in range(self._size):
            try:
                d = self._create_one()
                self._drivers.append(d)
                self._queue.put(d)
                logger.info("DriverPool: driver %d/%d ready", i + 1, self._size)
            except Exception as e:
                logger.warning("DriverPool: failed to create driver %d: %s", i + 1, e)
            # Small delay between driver creations to avoid chromedriver patch conflicts
            if i < self._size - 1:
                time.sleep(2)
        if not self._drivers:
            raise RuntimeError("DriverPool: could not create any drivers")
        actual = len(self._drivers)
        if actual < self._size:
            logger.warning("DriverPool: only %d/%d drivers created, continuing with reduced pool", actual, self._size)
            self._size = actual
        return self

    def _create_one(self):
        """Create a single driver and warm it with HLTV pages."""
        d = _create_driver_raw(headless=self._headless)
        # Warm up: resolve Cloudflare and verify driver stability
        # First nav resolves Cloudflare challenge
        d.get("https://www.hltv.org/ranking/teams")
        wait_for_cloudflare(d, timeout=25)
        random_delay(1.5, 2.5)
        # Second nav to a stats page — same domain pattern the workers use.
        # This catches RemoteDisconnected early so the driver is stable.
        try:
            d.get("https://www.hltv.org/stats")
            wait_for_cloudflare(d, timeout=15)
            random_delay(1.0, 2.0)
        except Exception as e:
            logger.warning("DriverPool warmup second nav failed: %s — replacing", e)
            try:
                d.quit()
            except Exception:
                pass
            # Create a fresh driver — the first one was unstable
            d = _create_driver_raw(headless=self._headless)
            d.get("https://www.hltv.org/ranking/teams")
            wait_for_cloudflare(d, timeout=25)
            random_delay(2.0, 3.0)
        return d

    def checkout(self, timeout=120):
        """Get a driver from the pool. Blocks until one is available."""
        d = self._queue.get(timeout=timeout)
        # If this driver was marked bad, replace it
        with self._lock:
            if id(d) in self._bad:
                self._bad.discard(id(d))
                self._drivers.remove(d)
                try:
                    d.quit()
                except Exception:
                    pass
                d = self._create_one()
                self._drivers.append(d)
        return d

    def checkin(self, driver):
        """Return a driver to the pool for reuse."""
        if not self._closed:
            self._queue.put(driver)

    def mark_bad(self, driver):
        """Mark a driver as stale so it gets replaced on next checkout."""
        with self._lock:
            self._bad.add(id(driver))

    def close(self):
        """Quit all drivers and clean up."""
        self._closed = True
        for d in self._drivers:
            try:
                d.quit()
            except Exception:
                pass
        self._drivers.clear()

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()
