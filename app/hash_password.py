"""Generate a password hash for APP_PASSWORD in secrets.env.

Usage:
    python app/hash_password.py

Paste the resulting hash as APP_PASSWORD in secrets.env. The login flow
(verify_password in flask_app.py) automatically detects and verifies the
hash, so no plain-text password is stored on the server.
"""
from getpass import getpass
from werkzeug.security import generate_password_hash

if __name__ == "__main__":
    pw1 = getpass("New password: ")
    pw2 = getpass("Repeat password: ")
    if pw1 != pw2:
        raise SystemExit("Passwords do not match.")
    if not pw1:
        raise SystemExit("Password cannot be empty.")
    print("\nAPP_PASSWORD=" + generate_password_hash(pw1))
