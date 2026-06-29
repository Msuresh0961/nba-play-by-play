from __future__ import annotations

import requests
from plyer import notification


WEBHOOK_URL = "your_url_here"


def send_discord(message):
    if not WEBHOOK_URL or WEBHOOK_URL == "your_url_here":
        return
    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
    except requests.RequestException:
        return


def send_desktop(message):
    try:
        notification.notify(title="NBA Alert", message=message, timeout=5)
    except Exception:
        return


def notify(message):
    send_discord(message)
    send_desktop(message)


if __name__ == "__main__":
    notify("Test NBA alert")

