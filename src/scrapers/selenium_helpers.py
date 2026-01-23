"""Shared Selenium helpers to avoid flooding Chrome sessions."""

from __future__ import annotations

import os
import threading


_MAX = int(os.getenv("SELENIUM_MAX_CONCURRENCY", "1"))
_SEMAPHORE = threading.Semaphore(_MAX)


def acquire_slot():
    _SEMAPHORE.acquire()


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


def release_slot():
    _SEMAPHORE.release()
