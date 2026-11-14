import logging
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

from ..events import Event
from . import AlertSink, ConsoleSink, WhatsAppSink

LOG = logging.getLogger(__name__)


class AlertNotifier:
    def __init__(self, whatsapp: bool) -> None:
        if whatsapp:
            load_dotenv()
        self.console = ConsoleSink()
        self.sink: AlertSink = WhatsAppSink(whatsapp)
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="alerts")

    def notify(self, event: Event) -> None:
        self.console.send(event)
        self.worker.submit(self._deliver, event)

    def _deliver(self, event: Event) -> None:
        if sys.platform == "darwin":
            try:
                subprocess.Popen(
                    ["/usr/bin/afplay", "/System/Library/Sounds/Glass.aiff"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                ).wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                LOG.debug("Could not play the alert sound", exc_info=True)
        self.sink.send(event)

    def close(self) -> None:
        self.worker.shutdown()
