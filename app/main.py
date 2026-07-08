import json
import logging
import re
import time
from pathlib import Path
from web import run_web

import requests
import yaml
from playwright.sync_api import sync_playwright

CONFIG_PATH = Path("/app/config.yml")
DATA_DIR = Path("/app/data")
SEEN_PATH = DATA_DIR / "seen.json"

from threading import Thread
from datetime import datetime, timedelta

STATUS_PATH = DATA_DIR / "status.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    force=True,
)
log = logging.getLogger("fb-marketplace-watcher")

DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    log.info("Loading config from %s", CONFIG_PATH)
    with CONFIG_PATH.open("r") as f:
        return yaml.safe_load(f)


def load_seen():
    if not SEEN_PATH.exists():
        log.info("No seen.json found; this is first run")
        return {}, True
    log.info("Loading seen IDs from %s", SEEN_PATH)
    return json.loads(SEEN_PATH.read_text()), False


def save_seen(seen):
    SEEN_PATH.write_text(json.dumps(seen, indent=2, sort_keys=True), encoding="utf-8")
    log.info("Saved seen IDs")

def save_status(status):
    STATUS_PATH.write_text(
        json.dumps(status, indent=2),
        encoding="utf-8",
    )

def send_telegram(bot_token, chat_id, text):
    log.info("Sending Telegram notification")
    api = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    r = requests.post(
        api,
        data={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": False,
        },
        timeout=20,
    )
    r.raise_for_status()


def fetch_ids(page, search):
    url = search["url"]
    name = search["name"]

    log.info("[%s] Opening search URL: %s", name, url)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    log.info("[%s] Waiting briefly for Marketplace results to load", name)
    page.wait_for_timeout(8000)

    html = page.content()
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_")
    html_path = DATA_DIR / f"{safe_name}.html"
    html_path.write_text(html, encoding="utf-8")
    log.info("[%s] Saved HTML to %s", name, html_path)

    ids = sorted(set(re.findall(r"/marketplace/item/(\d+)", html)))
    return ids


def scan_once():
    config = load_config()
    seen, first_run = load_seen()

    status = {
        "last_scan": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "next_scan": "",
    "searches": {},
    }
    bot_token = config["telegram"]["bot_token"]
    chat_id = config["telegram"]["chat_id"]

    searches = config.get("searches", [])
    log.info("Starting scan for %d searches", len(searches))

    with sync_playwright() as p:
        log.info("Launching Chromium")
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        page = browser.new_page()

        for search in searches:
            name = search["name"]
            seen.setdefault(name, [])

            try:
                ids = fetch_ids(page, search)
            except Exception as e:
                log.exception("[%s] Search failed: %s", name, e)
                continue

            old_ids = set(seen[name])
            new_ids = [item_id for item_id in ids if item_id not in old_ids]

            log.info("[%s] Found %d listings; %d new", name, len(ids), len(new_ids))
            status["searches"][name] = {
                "last_found": len(ids),
                "last_new": len(new_ids),
                "last_checked": datetime.now().strftime("%H:%M:%S"),
            }
            notify_first_run = search.get("notify_first_run", False)

            if first_run and not notify_first_run:
                log.info("[%s] First run; saving baseline without notifications", name)
            else:
                for item_id in new_ids:
                    item_url = f"https://www.facebook.com/marketplace/item/{item_id}/"
                    msg = f"🆕 {name}\n\n{item_url}"
                    send_telegram(bot_token, chat_id, msg)
                    time.sleep(1)

            seen[name] = sorted(set(seen[name]) | set(ids))

        browser.close()
        log.info("Chromium closed")

    status["next_scan"] = (
        datetime.now() + timedelta(minutes=config["watcher"]["interval_minutes"])
    ).strftime("%Y-%m-%d %H:%M:%S")

    save_status(status)

    save_seen(seen)


def main():
    config = load_config()
    interval = config.get("watcher", {}).get("interval_minutes", 360)

    log.info("Watcher starting; interval is %d minutes", interval)
    Thread(target=run_web, daemon=True).start()
    while True:
        try:
            scan_once()
        except Exception as e:
            log.exception("Scan crashed: %s", e)

        log.info("Sleeping for %d minutes", interval)
        time.sleep(interval * 60)


if __name__ == "__main__":
    main()
