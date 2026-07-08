import json
from pathlib import Path
from urllib.parse import quote

from flask import Flask, redirect, request

from storage import add_search, delete_search, load_all_searches, set_search_enabled

DATA_DIR = Path("/app/data")
STATUS_PATH = DATA_DIR / "status.json"
RUN_NOW_PATH = DATA_DIR / "run_now.json"

app = Flask(__name__)


def load_status():
    if not STATUS_PATH.exists():
        return {}
    return json.loads(STATUS_PATH.read_text())


@app.route("/")
def index():
    status = load_status()
    searches = load_all_searches()

    edit_name = request.args.get("edit")
    edit_search = None
    if edit_name:
        for search in searches:
            if search["name"] == edit_name:
                edit_search = search
                break

    form_name = edit_search.get("name", "") if edit_search else ""
    form_url = edit_search.get("url", "") if edit_search else ""
    form_interval = edit_search.get("interval_minutes", 360) if edit_search else 360

    form_email_value = edit_search.get("notify_email", "") if edit_search else ""
    if isinstance(form_email_value, list):
        form_email = ", ".join(form_email_value)
    else:
        form_email = form_email_value

    form_telegram_checked = "checked" if (not edit_search or edit_search.get("notify_telegram", True)) else ""
    form_enabled_checked = "checked" if (not edit_search or edit_search.get("enabled", True)) else ""

    rows = ""
    for search in searches:
        name = search["name"]
        s = status.get("searches", {}).get(name, {})
        toggle = "Disable" if search["enabled"] else "Enable"

        rows += f"""
        <tr>
            <td>{"✅" if search["enabled"] else "⏸️"} {name}</td>
            <td>{s.get("last_found", "-")}</td>
            <td>{s.get("last_new", "-")}</td>
            <td>{search.get("seen_count", 0)}</td>
            <td>{search.get("interval_minutes", 360)} min</td>
            <td>{s.get("last_checked", "-")}</td>
            <td><a href="{search["url"]}" target="_blank">Open</a></td>
            <td>
                <a href="/?edit={quote(name)}">Edit</a>
                &nbsp;
                <form method="post" action="/run-now" style="display:inline">
                    <input type="hidden" name="name" value="{name}">
                    <button>Run now</button>
                </form>
                &nbsp;
                <form method="post" action="/toggle" style="display:inline">
                    <input type="hidden" name="name" value="{name}">
                    <input type="hidden" name="enabled" value="{0 if search["enabled"] else 1}">
                    <button>{toggle}</button>
                </form>
                &nbsp;
                <form method="post" action="/delete" style="display:inline" onsubmit="return confirm('Delete this search and its seen history?')">
                    <input type="hidden" name="name" value="{name}">
                    <button>Delete</button>
                </form>
            </td>
        </tr>
        """

    return f"""
    <html>
    <head>
        <title>Marketplace Watcher</title>
        <style>
            body {{ font-family: sans-serif; margin: 2rem; max-width: 1200px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border-bottom: 1px solid #ddd; padding: 0.6rem; text-align: left; }}
            input {{ width: 100%; padding: 0.5rem; margin: 0.2rem 0 0.8rem; }}
            button {{ padding: 0.4rem 0.7rem; }}
            .ok {{ color: green; }}
            .card {{ border: 1px solid #ddd; padding: 1rem; margin-top: 1.5rem; border-radius: 8px; }}
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
                <th>Seen total</th>
                <th>Interval</th>
                <th>Last checked</th>
                <th>Search</th>
                <th>Action</th>
            </tr>
            {rows}
        </table>

        <div class="card">
            <h2>{"Edit Search" if edit_search else "Add / Update Search"}</h2>
            <form method="post" action="/add">
                <label>Name</label>
                <input name="name" value="{form_name}" required>

                <label>Facebook Marketplace search URL</label>
                <input name="url" value="{form_url}" required>

                <label>Scan interval, minutes</label>
                <input name="interval_minutes" type="number" min="5" value="{form_interval}" required>

                <label>
                    <input type="checkbox" name="notify_telegram" {form_telegram_checked} style="width:auto">
                    Telegram
                </label><br><br>

                <label>Email recipients, comma separated</label>
                <input name="notify_email" value="{form_email}" placeholder="carla@example.com">

                <label>
                    <input type="checkbox" name="enabled" {form_enabled_checked} style="width:auto">
                    Enabled
                </label><br><br>

                <button type="submit">Save search</button>
                {"<a href='/' style='margin-left:1rem'>Cancel edit</a>" if edit_search else ""}
            </form>
        </div>
    </body>
    </html>
    """


@app.route("/add", methods=["POST"])
def add():
    add_search(
        name=request.form["name"].strip(),
        url=request.form["url"].strip(),
        notify_telegram=request.form.get("notify_telegram") == "on",
        notify_email=request.form.get("notify_email", "").strip(),
        enabled=request.form.get("enabled") == "on",
        interval_minutes=request.form.get("interval_minutes", "360"),
    )
    return redirect("/")


@app.route("/toggle", methods=["POST"])
def toggle():
    set_search_enabled(
        request.form["name"],
        request.form["enabled"] == "1",
    )
    return redirect("/")


@app.route("/delete", methods=["POST"])
def delete():
    delete_search(request.form["name"])
    return redirect("/")


@app.route("/run-now", methods=["POST"])
def run_now():
    RUN_NOW_PATH.write_text(
        json.dumps({"search_name": request.form["name"]}),
        encoding="utf-8",
    )
    return redirect("/")


def run_web():
    app.run(host="0.0.0.0", port=8099, debug=False, use_reloader=False)
