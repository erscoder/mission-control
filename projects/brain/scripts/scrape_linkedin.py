#!/usr/bin/env python3
"""
scrape_linkedin.py — Scrape LinkedIn saved posts via Playwright + CDP
Requires: Docker container with Chromium running (docker compose up -d chromium)
Usage: python scripts/scrape_linkedin.py
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

CHROME_DEVTOOLS_URL = "http://localhost:3000"


async def scrape_linkedin_posts(headless: bool = True, scroll_limit: int = 10) -> list[dict]:
    """Scrape saved posts from LinkedIn using Playwright with CDP."""

    posts = []
    output_dir = Path("raw/linkedin-saved")
    output_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        # Connect to remote Chromium via CDP
        try:
            browser = await p.chromium.connect_over_cdp(CHROME_DEVTOOLS_URL)
        except Exception as e:
            print(f"[!] Could not connect to Chromium at {CHROME_DEVTOOLS_URL}")
            print(f"    Run: docker compose up -d chromium")
            print(f"    Error: {e}")
            return []

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

        page = await context.new_page()

        print("[*] Navigating to LinkedIn saved posts...")
        await page.goto("https://www.linkedin.com/my-items/saved-posts/", wait_until="networkidle")

        # Check if login required
        if "login" in page.url.lower():
            print("[!] Not logged in. Make sure Chromium has an authenticated session.")
            print("    Mount your LinkedIn session cookies into the Docker container.")
            await browser.close()
            return []

        print(f"[*] On page: {page.url}")

        # Scroll to load more posts
        last_height = 0
        scroll_count = 0
        seen_ids = set()

        while scroll_count < scroll_limit:
            # Wait for posts to load
            await page.wait_for_selector("div.feed-shared-update-v2", timeout=5000)

            # Get current posts
            post_elements = await page.query_selector_all("div.feed-shared-update-v2")

            for post_el in post_elements:
                try:
                    post_id = await post_el.get_attribute("data-id") or str(hash(await post_el.inner_text()[:100]))

                    if post_id in seen_ids:
                        continue
                    seen_ids.add(post_id)

                    # Extract post content
                    text_el = await post_el.query_selector("span.feed-shared-text")
                    text = await text_el.inner_text() if text_el else ""

                    author_el = await post_el.query_selector("span.feed-shared-actor__name")
                    author = await author_el.inner_text() if author_el else "Unknown"

                    time_el = await post_el.query_selector("time")
                    time_str = await time_el.get_attribute("datetime") if time_el else ""

                    # Get engagement metrics
                    reactions_el = await post_el.query_selector("button.feed-shared-social-actions__reaction-count")
                    reactions = await reactions_el.inner_text() if reactions_el else "0"

                    # Get links in post
                    links = []
                    link_els = await post_el.query_selector_all("a[href*='http']")
                    for link_el in link_els:
                        href = await link_el.get_attribute("href")
                        if href and "linkedin.com" not in href:
                            links.append(href)

                    posts.append({
                        "id": post_id,
                        "text": text,
                        "author": author,
                        "datetime": time_str,
                        "reactions": reactions,
                        "links": links[:5],
                        "scraped_at": datetime.utcnow().isoformat(),
                    })
                except Exception as e:
                    print(f"    [!] Error parsing post: {e}")
                    continue

            print(f"    [*] Collected {len(posts)} posts so far...")

            # Scroll down
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)

            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                print("[*] Reached bottom of page")
                break

            last_height = new_height
            scroll_count += 1

        await browser.close()

    # Save posts
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
    output_file = output_dir / f"{timestamp}.json"
    output_file.write_text(json.dumps(posts, indent=2, ensure_ascii=False))

    print(f"[+] Saved {len(posts)} posts to {output_file}")
    return posts


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape LinkedIn saved posts")
    parser.add_argument("--scroll-limit", type=int, default=10, help="Max scroll iterations")
    args = parser.parse_args()

    asyncio.run(scrape_linkedin_posts(scroll_limit=args.scroll_limit))
