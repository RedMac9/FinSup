"""WSGI entry point for production (Gunicorn).

Run from the FinRep2/ directory so that relative paths (secrets.env, CSV
files) resolve correctly, e.g.:

    gunicorn --workers 1 --threads 4 --bind 127.0.0.1:5000 wsgi:app

A single worker is required because run_procedure runs in a background
thread and logs are kept in an in-memory buffer (LogCapture); multiple
workers would not share that state.
"""
import os
import sys

# The Flask app lives in app/ and uses imports relative to that directory
# (e.g. `from main import run_procedure`), so app/ must be on sys.path.
APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app")
sys.path.insert(0, APP_DIR)

from flask_app import app  # noqa: E402

if __name__ == "__main__":
    app.run(port=5000)
