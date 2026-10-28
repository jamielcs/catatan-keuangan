import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")


def _get_secret_key():
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    os.makedirs(INSTANCE_DIR, exist_ok=True)
    path = os.path.join(INSTANCE_DIR, "secret_key.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    import secrets

    v = secrets.token_hex(32)
    with open(path, "w", encoding="utf-8") as f:
        f.write(v)
    return v


class Config:
    SECRET_KEY = None  # set in factory via _get_secret_key unless overridden
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(INSTANCE_DIR, "catatan_aprilcell.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # local http only
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 12
    WTF_CSRF_ENABLED = True
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key-for-pytest-only"
