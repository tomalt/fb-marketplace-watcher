import json
from pathlib import Path

import yaml
from flask import Flask

CONFIG_PATH = Path("/app/config.yml")
DATA_DIR = Path("/app/data")
STATUS_PATH = DATA_DIR / "status.json"

app = Flask(__name__)


def load_config():
    with CONFIG_PATH.open("r") as f:
        return yaml.safe_load(f)


def load_status():
    if not STATUS_PATH.exists():
        return {}
    return json.loads(STATUS_PATH.read_text())


@app.route("/")
def index():
    config = load_config()
    status = load_status()

    searches = config.get("searches", [])
    rows = ""

    for search in searches:
        name = search.get("name", "Unnamed")
        s = status.get("searches", {}).get(name, {})
        rows += f"""
        <tr>
            <td>{name}</td>
            <td>{s.get("last_found", "-")}</td>
            <td>{s.get("last_new", "-")}</td>
            <td>{s.get("last_checked", "-")}</td>
            <td><a href="{search.get("url", "#")}" target="_blank">Open</a></td>
        </tr>
        """

    return f"""
    <html>
    <head>
        <title>Marketplace Watcher</title>
        <style>
            body {{ font-family: sans-serif; margin: 2rem; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border-bottom: 1px solid #ddd; padding: 0.6rem; text-align: left; }}
            .ok {{ color: green; }}
        </style>
    </head>
    <body>
        <h1>Marketplace Watcher</h1>
        <p class="ok">Running</p>
        <p><strong>Last scan:</strong> {status.get("last_scan", "-")}</p>
        <p><strong>Next scan:</strong> {status.get("next_scan", "-")}</p>

        <h2>Searches</h2>
        <table>
            <tr>
                <th>Name</th>
                <th>Listings found</th>
                <th>New last scan</th>
                <th>Last checked</th>
                <th>Search</th>
            </tr>
            {rows}
        </table>
    </body>
    </html>
    """


def run_web():
    app.run(host="0.0.0.0", port=8099, debug=False, use_reloader=False)
