import queue

from flask import Flask, send_from_directory, render_template, abort, Response
import json
import os
import time
import urllib.error
import urllib.request
from dotenv import load_dotenv
import flask

from printer import PrusaPrinter

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

printers_list = [
    PrusaPrinter(name="Prusa Mini", url="http://127.0.0.1:4010", password="test"),
    PrusaPrinter(name="Prusa MK3S+", url="http://", password=""),
]

for printer in printers_list:
    printer.start()

@app.route("/")
def home_page():
    return app.send_static_file("index.html")

@app.route("/printer_<int:printer_id>.html")
def printer_detail(printer_id):
    if not 1 <= printer_id <= len(printers_list):
        abort(404)

    curr_printer = printers_list[printer_id - 1]  # IDs start at 1.
    return render_template("printer_detail.html", printer_details={
        "id": printer_id,
        "name": curr_printer.name,
        "files": [
            {"name": "file1.gcode", "status": "Finished"},
            {"name": "file2.gcode", "status": "In Progress"},
        ]
    })

@app.route("/api/printer/<int:printer_id>/info_stream")
def printer_info_stream(printer_id: int):
    if not 1 <= printer_id <= len(printers_list):
        abort(404)

    curr_printer = printers_list[printer_id - 1]  # IDs start at 1.
    info_queue: queue.Queue[str] = queue.Queue(maxsize=1)
    curr_printer.add_info_subscriber(info_queue)

    def info_events():
        try:
            while True:
                yield info_queue.get()
        finally:
            curr_printer.remove_info_subscriber(info_queue)

    return Response(
        info_events(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.route("/printers")
def printers_page():
    return app.send_static_file("printers.html")