import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread

import yaml
from playwright.sync_api import sync_playwright

from notifier import notify
from scanner import fetch_ids
from storage import load_seen, save_seen, save_status, init_searches_from_config, load_searches
from web import run_web

CONFIG_PATH = Path("/app/config.yml")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    force=True,
)
log = logging.getLogger("fb-marketplace-watcher")


def load_config():
    log.info("Loading config from %s", CONFIG_PATH)
    with CONFIG_PATH.open("r") as f:
        return yaml.safe_load(f)


def scan_once():
    config = load_config()
    seen, first_run = load_seen()

    interval = config.get("watcher", {}).get("interval_minutes", 360)
    init_searches_from_config(config.get("searches", []))
    searches = load_searches()

    status = {
        "last_scan": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "next_scan": "",
        "searches": {},
    }

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
                ids = fetch_ids(page, search, log)
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
                    notify(config, search, item_id, log)
                    time.sleep(1)

            seen[name] = sorted(set(seen[name]) | set(ids))

        browser.close()
        log.info("Chromium closed")

    status["next_scan"] = (
        datetime.now() + timedelta(minutes=interval)
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
