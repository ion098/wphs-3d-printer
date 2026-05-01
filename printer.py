import time
import json
import requests
import requests.auth
import threading
import queue
from urllib.parse import urljoin

class ThreeDPrinter:
    def __init__(self, name: str, url: str, password: str):
        self.name = name
        self.url = url
        self.username = "maker"
        self.password = password
        self.auth = requests.auth.HTTPDigestAuth(self.username, self.password)
        self.printer_queue = []
        self.info_updater_thread: threading.Thread | None = None
        self.info_subscribers: set[queue.Queue[str]] = set()

    def start(self):
        # Start the thread that updates printer info and notifies subscribers
        self.info_updater_thread = threading.Thread(target=self._update_info_loop, daemon=True)
        self.info_updater_thread.start()

    def _fetch_printer_info(self) -> str | None:
        try:
            response = requests.get(urljoin(self.url, "/api/v1/status"), auth=self.auth, timeout=10)
            response.raise_for_status()
            return response.text.replace("\n", "")
        except requests.RequestException as e:
            print(f"Error fetching printer info: {e}")
            return None

    def _update_info_loop(self):
        while True:
            # If there's an error fetching printer info, we send a line starting with ":" to keep
            # the connection alive. Lines that start with a colon are ignored by SSE.
            info = (self._fetch_printer_info() or ":") + "\n\n"

            for q in list(self.info_subscribers):
                # Update info for each subscriber
                q.put(info)

            time.sleep(5)  # Poll every 5 seconds