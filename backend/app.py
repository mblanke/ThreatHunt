from flask import Flask, send_from_directory
import os
app = Flask(__name__, static_folder="../frontend/dist")

@app.route("/assets/<path:path>")
def send_assets(path):
    return send_from_directory(os.path.join(app.static_folder, "assets"), path)

@app.route("/uploaded/<path:path>")
def send_uploads(path):
    return send_from_directory(os.path.join(app.static_folder, "assets"), path)

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
