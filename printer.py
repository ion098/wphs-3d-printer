import time
import json
import requests
import requests.auth
import threading
import queue
from urllib.parse import urljoin

class PrusaPrinter:
    def __init__(self, name: str, url: str, password: str):
        self.name = name
        self.url = url
        # All Prusa printers have a default username of "maker", so we hardcode it here.
        self.username = "maker"
        self.password = password
        self.auth = requests.auth.HTTPDigestAuth(self.username, self.password)
        self.info_updater_thread: threading.Thread | None = None
        self._info_subscribers: set[queue.Queue[str]] = set()
        self._info_subscribers_lock = threading.Lock()

    def add_info_subscriber(self, info_queue: queue.Queue[str]) -> None:
        with self._info_subscribers_lock:
            self._info_subscribers.add(info_queue)

    def remove_info_subscriber(self, info_queue: queue.Queue[str]) -> None:
        with self._info_subscribers_lock:
            self._info_subscribers.discard(info_queue)

    def get_info_subscribers(self) -> list[queue.Queue[str]]:
        with self._info_subscribers_lock:
            return list(self._info_subscribers)

    def start(self):
        # Start the thread that updates printer info and notifies subscribers
        self.info_updater_thread = threading.Thread(target=self._update_info_loop, daemon=True)
        self.info_updater_thread.start()

    def _fetch_printer_info(self) -> str | None:
        try:
            response = requests.get(urljoin(self.url, "/api/v1/status"), auth=self.auth, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching printer info: {e}")
            return None

    def _update_info_loop(self):
        while True:
            subscribers = self.get_info_subscribers()
            info = None
            if subscribers:
                # Only fetch printer info if there are active subscribers to avoid unnecessary API calls.
                info = self._fetch_printer_info()
            # If there's an error fetching printer info, we send a line starting with ":" to keep
            # the connection alive. Lines that start with a colon are ignored by SSE.
            info = f"data:{info.replace('\n', '')}\n\n" if info else ":\n\n"

            for q in subscribers:
                # Update info for each subscriber
                try:
                    q.put_nowait(info)
                except queue.Full:
                    # Drop stale data for slow clients and keep only the latest event.
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        pass

            time.sleep(2)  # Poll every 2 seconds