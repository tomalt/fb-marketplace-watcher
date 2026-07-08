import re
from pathlib import Path

DATA_DIR = Path("/app/data")


def fetch_ids(page, search, log):
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

    return sorted(set(re.findall(r"/marketplace/item/(\d+)", html)))
