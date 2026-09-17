"""Where the bot talks to you.

In alert-only mode this *is* the execution path, so it has to be reliable: if a
notification fails to send, the failure is raised rather than swallowed.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Protocol, runtime_checkable


@runtime_checkable
class Notifier(Protocol):
    def send(self, message: str) -> None: ...


class ConsoleNotifier:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, message: str) -> None:
        self.sent.append(message)
        print(message)


class TelegramNotifier:
    """Minimal Telegram sender.

    Credentials come from the environment (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) -
    never commit them.
    """

    API = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, token: str | None = None, chat_id: str | None = None, timeout: float = 10.0) -> None:
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.timeout = timeout
        if not self.token or not self.chat_id:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set to use TelegramNotifier"
            )

    def send(self, message: str) -> None:  # pragma: no cover - network
        payload = json.dumps({"chat_id": self.chat_id, "text": message}).encode()
        request = urllib.request.Request(
            self.API.format(token=self.token),
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            if response.status != 200:
                raise RuntimeError(f"Telegram send failed with HTTP {response.status}")
