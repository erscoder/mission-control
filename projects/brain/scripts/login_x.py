#!/usr/bin/env python3
"""
login_x.py — Login to X and save session cookies for future use.
Run this once, then scrape_x_bookmarks.py will reuse the session.
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


async def login_x():
    """Interactively login to X and save session."""

    session_file = Path("session.json")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("[*] Opening x.com...")
        await page.goto("https://x.com/i/flow/login", wait_until="networkidle")

        print("[*] Please login manually in the browser window...")
        print("[*] Waiting for login to complete (will auto-detect)...")

        # Wait for login to complete (URL changes from login flow)
        await page.wait_for_url(lambda url: "x.com" in url and "login" not in url.lower(), timeout=120_000)

        print(f"[+] Logged in! URL: {page.url}")

        # Save cookies for future sessions
        cookies = await context.cookies()
        session_file.write_text(json.dumps({"cookies": cookies}, indent=2))
        print(f"[+] Session saved to {session_file}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(login_x())
