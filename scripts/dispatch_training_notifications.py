from __future__ import annotations

import os

import requests


endpoint = os.getenv(
    "TRAINING_NOTIFICATION_DISPATCH_URL",
    "https://sanosync.onrender.com/notifications/training/dispatch",
).strip()
secret = os.getenv("TRAINING_NOTIFICATION_CRON_SECRET", "").strip()

if not secret:
    raise RuntimeError("TRAINING_NOTIFICATION_CRON_SECRET is not configured")

response = requests.post(
    endpoint,
    headers={"X-Cron-Secret": secret},
    timeout=55,
)
response.raise_for_status()
print(response.json())
