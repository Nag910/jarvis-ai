import os, secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Optional: export SECRET_KEY to keep sessions valid across restarts.
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    DATABASE = os.path.join(BASE_DIR, "instance", "jarvis.db")
    MAX_CONTENT_LENGTH = 64 * 1024  # reject huge request bodies
