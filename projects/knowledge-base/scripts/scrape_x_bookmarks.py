#!/usr/bin/env python3
"""
scrape_x_bookmarks.py — Download X bookmarks via Playwright
Usage: python scripts/scrape_x_bookmarks.py
"""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright


async def scrape_x_bookmarks(headless: bool = True, scroll_limit: int = 50) -> list[dict]:
    """Scrape bookmarks from X using Playwright with authenticated session."""

    bookmarks = []
    bookmarks_file = Path("raw/x-bookmarks/bookmarks.json")
    session_file = Path("session.json")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()

        # Load existing session if available (cookies from previous login)
        if session_file.exists():
            session_data = json.loads(session_file.read_text())
            await context.add_cookies(session_data.get("cookies", []))
            print(f"[+] Session loaded from {session_file}")
        else:
            print("[!] No session found. Please login to X first.")
            print("    Run: python scripts/login_x.py")
            await browser.close()
            return []

        page = await context.new_page()
        await page.goto("https://x.com/i/bookmarks", wait_until="networkidle")

        # Check if login required
        if "login" in page.url.lower():
            print("[!] Not authenticated. Please run login_x.py first.")
            await browser.close()
            return []

        print(f"[*] On bookmarks page: {page.url}")

        # Scroll to load more bookmarks
        last_height = 0
        scroll_count = 0
        seen_ids = set()

        while scroll_count < scroll_limit:
            # Get current tweets
            tweets = await page.query_selector_all('article[data-testid="tweet"]')
            for tweet in tweets:
                try:
                    tweet_id = await tweet.get_attribute("data-tweet-id")
                    if tweet_id in seen_ids:
                        continue
                    seen_ids.add(tweet_id)

                    # Extract tweet data
                    text_el = await tweet.query_selector('[data-testid="tweetText"]')
                    text = await text_el.inner_text() if text_el else ""

                    author_el = await tweet.query_selector('[data-testid="User-Name"]')
                    author = await author_el.inner_text() if author_el else ""

                    time_el = await tweet.query_selector("time")
                    datetime_str = await time_el.get_attribute("datetime") if time_el else ""

                    # Get metrics
                    reply_el = await tweet.query_selector('[data-testid="reply"]')
                    reply_count = await reply_el.inner_text() if reply_el else "0"

                    retweet_el = await tweet.query_selector('[data-testid="retweet"]')
                    retweet_count = await retweet_el.inner_text() if retweet_el else "0"

                    like_el = await tweet.query_selector('[data-testid="like"]')
                    like_count = await like_el.inner_text() if like_el else "0"

                    # Get links
                    links = []
                    link_els = await tweet.query_selector_all('a[href*="http"]')
                    for link in link_els:
                        href = await link.get_attribute("href")
                        if href and not href.startswith("/"):
                            links.append(href)

                    bookmarks.append({
                        "id": tweet_id,
                        "text": text,
                        "author": author,
                        "datetime": datetime_str,
                        "reply_count": reply_count,
                        "retweet_count": retweet_count,
                        "like_count": like_count,
                        "links": links,
                        "scraped_at": datetime.utcnow().isoformat(),
                    })
                except Exception as e:
                    print(f"    [!] Error parsing tweet: {e}")
                    continue

            print(f"    [*] Collected {len(bookmarks)} bookmarks so far...")

            # Scroll down
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                print("[*] Reached bottom of page")
                break

            last_height = new_height
            scroll_count += 1

        await browser.close()

    # Save raw bookmarks
    output_dir = Path("raw/x-bookmarks")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
    output_file = output_dir / f"{timestamp}.json"

    output_file.write_text(json.dumps(bookmarks, indent=2, ensure_ascii=False))
    print(f"[+] Saved {len(bookmarks)} bookmarks to {output_file}")

    # Also update persistent bookmarks.json
    all_bookmarks = []
    if bookmarks_file.exists():
        all_bookmarks = json.loads(bookmarks_file.read_text())

    existing_ids = {b["id"] for b in all_bookmarks}
    new_bookmarks = [b for b in bookmarks if b["id"] not in existing_ids]

    if new_bookmarks:
        all_bookmarks.extend(new_bookmarks)
        bookmarks_file.write_text(json.dumps(all_bookmarks, indent=2, ensure_ascii=False))
        print(f"[+] Added {len(new_bookmarks)} NEW bookmarks to persistent store")
        print(f"    Total bookmarks: {len(all_bookmarks)}")
    else:
        print("[*] No new bookmarks to add")

    return bookmarks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape X bookmarks via Playwright")
    parser.add_argument("--visible", action="store_true", help="Show browser window")
    parser.add_argument("--scroll-limit", type=int, default=50, help="Max scroll iterations")
    args = parser.parse_args()

    asyncio.run(scrape_x_bookmarks(headless=not args.visible, scroll_limit=args.scroll_limit))
