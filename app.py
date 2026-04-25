from flask import Flask, send_from_directory, abort

app = Flask(__name__, static_folder='static', static_url_path='/')

@app.route("/")
def home_page():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/printers")
def printers_page():
    return send_from_directory(app.static_folder, "printers.html")

@app.route("/printer/<int:printer_id>")
def printer_detail(printer_id):
    if printer_id == 1:
        return send_from_directory(app.static_folder, "printer1.html")
    elif printer_id == 2:
        return send_from_directory(app.static_folder, "printer2.html")
    abort(404)

