from flask import Flask, send_from_directory, render_template, abort

app = Flask(__name__, static_folder='static', static_url_path='/')

@app.route("/")
def home_page():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/printer_<int:printer_id>.html")
def printer_detail(printer_id):
    if printer_id == 1:
        return render_template("printer_detail.html", printer={
            "id": 1,
            "name": "Prusa Mini",
            "files": [
                {"name": "file1.gcode", "status": "Finished"},
                {"name": "file2.gcode", "status": "In Progress"},
            ]
        })
    elif printer_id == 2:
        return render_template("printer_detail.html", printer={
            "id": 2,
            "name": "Prusa MK3S+",
            "files": [
                {"name": "file3.gcode", "status": "Finished"},
                {"name": "file4.gcode", "status": "Queued"},
            ]
        })
    abort(404)

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