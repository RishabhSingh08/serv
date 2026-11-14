import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from time import time
from typing import Protocol

import httpx

from ..events import Event

LOG = logging.getLogger(__name__)


class AlertSink(Protocol):
    def send(self, event: Event) -> None: ...


class ConsoleSink:
    def send(self, event: Event) -> None:
        level = logging.WARNING if event.severity == "warning" else logging.INFO
        LOG.log(level, "%s", event.message)


class JsonlSink:
    def __init__(self, directory: Path, filename: str = "events.jsonl") -> None:
        self.file = directory / filename

    def send(self, event: Event) -> None:
        with self.file.open("a", encoding="utf-8") as output:
            output.write(json.dumps(asdict(event)) + "\n")


class WhatsAppSink:
    def __init__(self, enabled: bool = True) -> None:
        self.sid = os.getenv("TWILIO_ACCOUNT_SID") if enabled else None
        self.token = os.getenv("TWILIO_AUTH_TOKEN") if enabled else None
        self.sender = os.getenv("TWILIO_WHATSAPP_FROM") if enabled else None
        self.recipient = os.getenv("TWILIO_WHATSAPP_TO") if enabled else None

    def send(self, event: Event) -> None:
        body = f"{event.message} Evidence is available in the local dashboard."
        if not (self.sid and self.token and self.sender and self.recipient):
            LOG.info("WhatsApp preview: %s", body)
            return
        try:
            response = httpx.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json",
                auth=(self.sid, self.token),
                data={
                    "From": "whatsapp:" + self.sender.removeprefix("whatsapp:"),
                    "To": "whatsapp:" + self.recipient.removeprefix("whatsapp:"),
                    "Body": body,
                },
                timeout=5,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            LOG.warning("WhatsApp delivery failed (HTTP %d). Message: %s", exc.response.status_code, body)
        except httpx.RequestError:
            LOG.warning("WhatsApp delivery failed. Message: %s", body)
        else:
            LOG.info("WhatsApp message accepted by Twilio.")


def expire_snapshots(directory: Path, days: int) -> None:
    cutoff = time() - days * 86400
    for path in directory.glob("*.jpg"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError as error:
            LOG.warning("Could not expire snapshot %s: %s", path.name, error)
