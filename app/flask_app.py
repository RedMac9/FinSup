import sys
import collections
import csv
import json
import logging
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.security import check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
import threading
from main import run_procedure
from output.graph import graph_start
from output.trade_txn_editor import trade_txn_editor_start
from output.positions_chart import positions_chart_start
from tickers_lists.ticker_groups import default_filter_graph

# Load environment variables from secrets.env located in the app root (FinRep2)
secrets_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'secrets.env'))
load_dotenv(secrets_path)

# Suppress Flask/Werkzeug logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# --- Required secrets (no insecure fallbacks) -------------------------------
# All of these MUST be provided via secrets.env. Missing values abort startup
# instead of silently falling back to predictable/default credentials.
APP_SECRET_KEY = os.environ.get("APP_SECRET_KEY")
APP_USERNAME = os.environ.get("APP_USERNAME")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

_missing = [name for name, val in (
    ("APP_SECRET_KEY", APP_SECRET_KEY),
    ("APP_USERNAME", APP_USERNAME),
    ("APP_PASSWORD", APP_PASSWORD),
) if not val]
if _missing:
    raise RuntimeError(
        "Missing required environment variables: "
        + ", ".join(_missing)
        + f". Define them in {secrets_path}."
    )

app.secret_key = APP_SECRET_KEY

# --- Session cookie hardening ----------------------------------------------
# SECURE requires HTTPS. Behind the nginx/TLS reverse proxy it stays on.
# For local HTTP testing set FLASK_SESSION_SECURE=0 (otherwise the browser
# will not send the cookie back and login will appear to fail).
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FLASK_SESSION_SECURE", "1") != "0",
)

# Trust the single reverse proxy (nginx) in front of the app so that
# request.remote_addr / X-Forwarded-For resolve to the real client IP.
# This makes the auth log and the rate limiter key off the actual visitor.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# --- Rate limiting ----------------------------------------------------------
# In-memory storage is fine because we run a single Gunicorn worker.
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

AUTH_LOG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'auth_log.csv'))
AUTH_LOG_FIELDS = [
    'timestamp_utc', 'result', 'username_provided', 'ip_address',
    'forwarded_for', 'user_agent', 'referer', 'method',
    'host', 'accept_language', 'session_id'
]

def _ensure_auth_log():
    if not os.path.exists(AUTH_LOG_PATH):
        with open(AUTH_LOG_PATH, 'w', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=AUTH_LOG_FIELDS).writeheader()

def log_auth_attempt(result: str, username_provided: str):
    _ensure_auth_log()
    row = {
        'timestamp_utc':      datetime.now(timezone.utc).isoformat(),
        'result':             result,
        'username_provided':  username_provided,
        'ip_address':         request.remote_addr,
        'forwarded_for':      request.headers.get('X-Forwarded-For', ''),
        'user_agent':         request.headers.get('User-Agent', ''),
        'referer':            request.headers.get('Referer', ''),
        'method':             request.method,
        'host':               request.host,
        'accept_language':    request.headers.get('Accept-Language', ''),
        'session_id':         request.cookies.get('session', ''),
    }
    with open(AUTH_LOG_PATH, 'a', newline='', encoding='utf-8') as f:
        csv.DictWriter(f, fieldnames=AUTH_LOG_FIELDS).writerow(row)

# Password verification helper (supports plain text and hashes)
def verify_password(stored_password_or_hash, password_input):
    if not stored_password_or_hash:
        return False
    try:
        if check_password_hash(stored_password_or_hash, password_input):
            return True
    except Exception:
        pass
    return stored_password_or_hash == password_input

# Require authentication for all routes except /login and static files
@app.before_request
def require_login():
    if request.path == '/login' or request.path.startswith('/static/'):
        return
    if not session.get('logged_in'):
        return redirect(url_for('login', next=request.path))

def _safe_next(next_url):
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return next_url
    return url_for('index')

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute; 50 per hour", methods=["POST"])
def login():
    next_url = _safe_next(request.args.get('next') or request.form.get('next'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == APP_USERNAME and verify_password(APP_PASSWORD, password):
            session['logged_in'] = True
            log_auth_attempt('SUCCESS', username)
            flash("Successfully logged in.")
            return redirect(next_url)
        else:
            log_auth_attempt('FAILURE', username or '')
            flash("Invalid username or password.")
            return render_template('login.html', next_url=next_url)

    return render_template('login.html', next_url=next_url)

@app.route('/logout')
def logout():
    session.clear()
    flash("Successfully logged out.")
    return redirect(url_for('login'))

# Log capture mechanism
class LogCapture:
    def __init__(self, maxlen=200):
        self.logs = collections.deque(maxlen=maxlen)
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        sys.stdout = self
        sys.stderr = self

    def write(self, data):
        if data.strip():
            self.logs.append(data.strip())
        self.stdout.write(data)

    def flush(self):
        self.stdout.flush()

    def get_logs(self):
        return list(self.logs)

log_capture = LogCapture()

# Initialize Dash apps attached to the Flask server
# These need to be initialized at startup
graph_choices = ["5", "6", "10", "7", "13"]
for choice in graph_choices:
    # Use a dummy list for initialization, can be adjusted if needed
    graph_start(choice, default_filter_graph(None), server=app)

trade_txn_editor_start(server=app)
positions_chart_start(server=app)

@app.route('/')
def index():
    procedures = [
        {"id": "1", "name": "GPW Update", "description": "Update GPW market metrics and Google Sheets."},
        {"id": "2", "name": "S&P500 Update", "description": "Update S&P500 market metrics and Google Sheets."},
        {"id": "3", "name": "US Update", "description": "Update US (NYSE + NASDAQ, ex S&P500) metrics and Google Sheets."},
        {"id": "4", "name": "Fast PROD", "description": "Run full production update (Exchange rates, DB, GSheet, Push)."},
        {"id": "9", "name": "Push Notification Test", "description": "Send a test notification via Pushbullet."},
        {"id": "12", "name": "ETF Update", "description": "Update ETF metrics and Google Sheets."},
        {"id": "14", "name": "Exchange Rates & DB", "description": "Update exchange rates and sync metrics to database."},
    ]
    
    dash_tools = [
        {"id": "5", "name": "Graph GPW", "url": "/graph/5/"},
        {"id": "6", "name": "Graph S&P 500", "url": "/graph/6/"},
        {"id": "10", "name": "Graph US", "url": "/graph/10/"},
        {"id": "7", "name": "Graph PROD", "url": "/graph/7/"},
        {"id": "13", "name": "Graph ETF", "url": "/graph/13/"},
        {"id": "15", "name": "Trade Txn Editor", "url": "/trade_txn_editor/"},
        {"id": "16", "name": "Open Positions Chart", "url": "/positions_chart/"},
    ]
    
    return render_template('index.html', procedures=procedures, dash_tools=dash_tools)

ALLOWED_PROCEDURES = {"1", "2", "3", "4", "9", "12", "14"}

@app.route('/run/<procedure_id>', methods=['POST'])
def run_proc(procedure_id):
    if procedure_id not in ALLOWED_PROCEDURES:
        return "Not found", 404
    thread = threading.Thread(target=run_procedure, args=(procedure_id,))
    thread.start()
    flash(f"Procedure {procedure_id} started in the background.")
    return redirect(url_for('index'))

@app.route('/logs')
def get_logs():
    return jsonify(log_capture.get_logs())

if __name__ == '__main__':
    # Local development only. In production the app is served by Gunicorn
    # via wsgi.py (see deployment plan) — never with debug=True exposed.
    print("\n" + "="*50)
    print("  FinSup2 ENGINE STARTING (dev server)")
    print("  Dashboard: http://127.0.0.1:5000")
    print("="*50 + "\n")
    debug_enabled = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_enabled, port=5000, use_reloader=False)
