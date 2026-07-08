import smtplib
from email.message import EmailMessage

import requests


def send_telegram(config, text, log):
    telegram = config.get("telegram", {})
    bot_token = telegram["bot_token"]
    chat_id = telegram["chat_id"]

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


def send_email(config, recipients, subject, body, log):
    if not recipients:
        return

    email_cfg = config.get("email")
    if not email_cfg:
        log.warning("Email requested but no email config exists")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_cfg["from"]
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    log.info("Sending email to %s", ", ".join(recipients))

    with smtplib.SMTP(email_cfg["smtp_server"], email_cfg["smtp_port"], timeout=30) as smtp:
        smtp.starttls()
        smtp.login(email_cfg["smtp_username"], email_cfg["smtp_password"])
        smtp.send_message(msg)


def notify(config, search, item_id, log):
    name = search["name"]
    item_url = f"https://www.facebook.com/marketplace/item/{item_id}/"

    notify_cfg = search.get("notify", {})
    telegram_enabled = notify_cfg.get("telegram", True)
    email_recipients = notify_cfg.get("email", [])

    text = f"🆕 {name}\n\n{item_url}"

    if telegram_enabled:
        send_telegram(config, text, log)

    if email_recipients:
        subject = f"New Marketplace listing: {name}"
        body = f"New Marketplace listing for:\n\n{name}\n\n{item_url}\n\nSearch:\n{search['url']}"
        send_email(config, email_recipients, subject, body, log)
