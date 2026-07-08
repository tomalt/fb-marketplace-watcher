import json
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
DATA_DIR = Path("/app/data")
RUN_NOW_PATH = DATA_DIR / "run_now.json"

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


def load_run_now():
    if not RUN_NOW_PATH.exists():
        return None

    try:
        data = json.loads(RUN_NOW_PATH.read_text(encoding="utf-8"))
        return data.get("search_name")
    except Exception:
        log.exception("Could not read run-now request")
        return None
    finally:
        try:
            RUN_NOW_PATH.unlink()
        except FileNotFoundError:
            pass


def should_run_search(search, now, last_run_times, run_now_name):
    name = search["name"]

    if run_now_name == name:
        return True

    last_run = last_run_times.get(name)
    if last_run is None:
        return True

    interval = int(search.get("interval_minutes", 360) or 360)
    return now >= last_run + timedelta(minutes=interval)


def scan_once(last_run_times):
    config = load_config()
    seen, first_run = load_seen()

    init_searches_from_config(config.get("searches", []))
    searches = load_searches()

    now = datetime.now()
    run_now_name = load_run_now()

    due_searches = [
        search for search in searches
        if should_run_search(search, now, last_run_times, run_now_name)
    ]

    next_due = None
    for search in searches:
        name = search["name"]
        last_run = last_run_times.get(name, now)
        interval = int(search.get("interval_minutes", 360) or 360)
        due_at = last_run + timedelta(minutes=interval)
        if next_due is None or due_at < next_due:
            next_due = due_at

    status = {
        "last_scan": now.strftime("%Y-%m-%d %H:%M:%S"),
        "next_scan": next_due.strftime("%Y-%m-%d %H:%M:%S") if next_due else "",
        "searches": {},
    }

    if not due_searches:
        log.info("No searches due")
        save_status(status)
        return

    log.info("Starting scan for %d due searches", len(due_searches))

    with sync_playwright() as p:
        log.info("Launching Chromium")
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        page = browser.new_page()

        for search in due_searches:
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
            last_run_times[name] = datetime.now()

        browser.close()
        log.info("Chromium closed")

    save_status(status)
    save_seen(seen)


def main():
    config = load_config()
    fallback_interval = config.get("watcher", {}).get("interval_minutes", 360)

    log.info("Watcher starting; fallback interval is %d minutes", fallback_interval)

    Thread(target=run_web, daemon=True).start()

    last_run_times = {}

    while True:
        try:
            scan_once(last_run_times)
        except Exception as e:
            log.exception("Scan crashed: %s", e)

        log.info("Sleeping for 60 seconds")
        time.sleep(60)


if __name__ == "__main__":
    main()
