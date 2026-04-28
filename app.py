from flask import Flask, send_from_directory, abort

app = Flask(__name__, static_folder='static', static_url_path='/')

@app.route("/")
def home_page():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/printers")
def printers_page():
    return send_from_directory(app.static_folder, "printers.html")

@app.route("/printer1")
def printer1_detail():
    return send_from_directory(app.static_folder, "printer1.html")

@app.route("/printer2")
def printer2_detail():
    return send_from_directory(app.static_folder, "printer2.html")