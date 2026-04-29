from flask import Flask, send_from_directory, abort, Response
import json
import os
import time
import urllib.error
import urllib.request
from dotenv import load_dotenv

app = Flask(__name__, static_folder='static', static_url_path='/')

load_dotenv()

VALID_PRINTER_IDS = {1, 2}
PRUSALINK_BASE_URL = os.getenv("PRUSALINK_BASE_URL", "http://127.0.0.1")
PRUSALINK_USERNAME = os.getenv("PRUSALINK_USERNAME", "")
PRUSALINK_PASSWORD = os.getenv("PRUSALINK_PASSWORD", "")
STATUS_PATH = "/api/v1/status"
POLL_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 8
MAX_BACKOFF_SECONDS = 15

@app.route("/")
def home_page():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/printer/<int:printer_id>")
def printer_detail(printer_id):
    if printer_id == 1:
        return send_from_directory(app.static_folder, "printer1.html")
    elif printer_id == 2:
        return send_from_directory(app.static_folder, "printer2.html")
    abort(404)


def temperature_events(printer_id):
    status_url = f"{PRUSALINK_BASE_URL.rstrip('/')}{STATUS_PATH}"
    opener = urllib.request.build_opener()
    if PRUSALINK_USERNAME and PRUSALINK_PASSWORD:
        password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(
            realm="Printer API",
            uri=status_url,
            user=PRUSALINK_USERNAME,
            passwd=PRUSALINK_PASSWORD,
        )
        digest_handler = urllib.request.HTTPDigestAuthHandler(password_manager)
        opener = urllib.request.build_opener(digest_handler)

    last_temperature_c = None
    consecutive_failures = 0

    while True:
        temperature_c = None
        error = None
        stale = False
        try:
            with opener.open(status_url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
            temperature_c = data.get("printer", {}).get("temp_nozzle")
            if isinstance(temperature_c, (int, float)):
                last_temperature_c = float(temperature_c)
            consecutive_failures = 0
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            error = str(exc)
            consecutive_failures += 1
        except ValueError:
            error = "Invalid JSON response from PrusaLink status endpoint"
            consecutive_failures += 1

        if temperature_c is None and last_temperature_c is not None:
            temperature_c = last_temperature_c
            stale = True

        payload = {
            "printer_id": printer_id,
            "temperature_c": temperature_c,
            "timestamp": int(time.time()),
            "source_url": status_url,
            "error": error,
            "stale": stale,
            "consecutive_failures": consecutive_failures,
        }
        yield f"data: {json.dumps(payload)}\n\n"
        if consecutive_failures == 0:
            time.sleep(POLL_SECONDS)
        else:
            backoff = min(MAX_BACKOFF_SECONDS, POLL_SECONDS * (2 ** min(consecutive_failures, 3)))
            time.sleep(backoff)


@app.route("/api/printer/<int:printer_id>/temperature/stream")
def printer_temperature_stream(printer_id):
    if printer_id not in VALID_PRINTER_IDS:
        abort(404)
    return Response(
        temperature_events(printer_id),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.route("/printers")
def printers_page():
    return send_from_directory(app.static_folder, "printers.html")

'''
@app.route("/printer1")
def printer1_detail():
    return send_from_directory(app.static_folder, "printer1.html")

@app.route("/printer2")
def printer2_detail():
    return send_from_directory(app.static_folder, "printer2.html")
'''