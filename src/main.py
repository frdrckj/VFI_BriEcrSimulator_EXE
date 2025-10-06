import os
import sys
import webbrowser
import threading
import time
from flask import Flask, send_from_directory
from flask_cors import CORS
from src.routes.ecr import ecr_bp


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# Set static folder to work with PyInstaller
static_path = get_resource_path("src/static")
app = Flask(__name__, static_folder=static_path)

CORS(app, origins=["*"], supports_credentials=True)
app.register_blueprint(ecr_bp, url_prefix="/api")


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    # Serve requested file or index.html
    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, "index.html")
        else:
            return "index.html not found", 404


def open_browser():
    """Open the default web browser to localhost:5001 after a short delay"""
    time.sleep(1.5)  # Wait for Flask to start up
    webbrowser.open("http://localhost:5001")


if __name__ == "__main__":
    # Start a thread to open the browser after Flask starts
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=5001, debug=False)
