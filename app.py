from flask import Flask, send_from_directory

app = Flask(__name__, static_folder='static', static_url_path='/')

@app.route("/")
def home_page():
    return send_from_directory(app.static_folder, "index.html")
