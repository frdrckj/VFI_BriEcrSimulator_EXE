import os
import sys
import webbrowser
import threading
import time
from flask import Flask, send_from_directory, session, redirect
from flask_cors import CORS
from flask_session import Session
from src.routes.ecr import ecr_bp
from src.routes.auth import auth_bp
from src.models.user import db

# Development setting: Set to False to bypass login
REQUIRE_LOGIN = True


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

# Set up database path - use current directory for writable database
db_dir = os.path.join(os.getcwd(), "src", "database")
os.makedirs(db_dir, exist_ok=True)
db_path = os.path.join(db_dir, "app.db")

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "asdf#FGSgvasgf$5$WGT")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["REQUIRE_LOGIN"] = REQUIRE_LOGIN

# Initialize extensions
Session(app)
db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()

CORS(app, origins=["*"], supports_credentials=True)
app.register_blueprint(ecr_bp, url_prefix="/api")
app.register_blueprint(auth_bp, url_prefix="/api/auth")


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    # Allow access to login page and auth-related files (but not root path if authenticated)
    if path in ["login.html", "style.css", "qrcode.min.js"] or path.startswith("login"):
        if path == "login" or path == "login.html":
            login_path = os.path.join(static_folder_path, "login.html")
            if os.path.exists(login_path):
                return send_from_directory(static_folder_path, "login.html")
        elif os.path.exists(os.path.join(static_folder_path, path)):
            return send_from_directory(static_folder_path, path)

    # Check authentication for main app
    if REQUIRE_LOGIN and "user_id" not in session:
        login_path = os.path.join(static_folder_path, "login.html")
        if os.path.exists(login_path):
            return send_from_directory(static_folder_path, "login.html")
        else:
            return "login.html not found", 404

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
