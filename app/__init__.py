import os
from flask import Flask, redirect, url_for, session
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

from extensions import db, migrate, csrf
from config import Config, _get_secret_key, BASE_DIR


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SEED_ACCOUNTS = [
    ("BCA", "BCA", "bank"),
    ("BRI", "BRI", "bank"),
    ("BNI", "BNI", "bank"),
    ("Mandiri", "Mandiri", "bank"),
    ("SeaBank", "SeaBank", "bank"),
    ("AlloBank", "AlloBank", "bank"),
    ("GoPay", "GoPay", "ewallet"),
    ("DANA Rudi", "DANA Rudi", "ewallet"),
    ("DANA Tamara", "DANA Tamara", "ewallet"),
    ("Uang", "Uang", "cash"),
    ("Cash", "Cash", "cash"),
]
SEED_CATEGORIES = [
    "Belanja rumah", "Makanan", "Transportasi", "Anak 1", "Anak 2", "Istri",
    "Tagihan", "Kesehatan", "Pendidikan", "Pulsa dan internet", "Kebutuhan pribadi", "Lain-lain",
]
SEED_PEOPLE = ["Anak 1", "Anak 2", "Istri"]


def seed_data():
    from app.models import Account, ExpenseCategory, Person
    if Account.query.count() == 0:
        for name, short, typ in SEED_ACCOUNTS:
            db.session.add(Account(name=name, short_name=short, account_type=typ, balance=0, initial_balance=0))
    if ExpenseCategory.query.count() == 0:
        for n in SEED_CATEGORIES:
            db.session.add(ExpenseCategory(name=n))
    if Person.query.count() == 0:
        for n in SEED_PEOPLE:
            db.session.add(Person(name=n))
    db.session.commit()


def create_app(config_class=None, config_overrides=None):
    app = Flask(__name__)
    cfg = config_class or Config
    app.config.from_object(cfg)
    if getattr(cfg, "SECRET_KEY", None) is None:
        app.config["SECRET_KEY"] = _get_secret_key()
    if config_overrides:
        app.config.update(config_overrides)

    os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, "backups"), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from app.utils import rupiah
    app.jinja_env.filters["rupiah"] = rupiah
    app.jinja_env.globals["rupiah"] = rupiah

    # blueprints
    from app.auth.routes import bp as auth_bp
    from app.dashboard.routes import bp as dash_bp
    from app.accounts.routes import bp as accounts_bp
    from app.transactions.routes import bp as tx_bp
    from app.transfers.routes import bp as transfers_bp
    from app.debts.routes import bp as debts_bp
    from app.expenses.routes import bp as expenses_bp
    from app.uncollected_income.routes import bp as unc_bp
    from app.reports.routes import bp as reports_bp
    from app.backup.routes import bp as backup_bp
    from app.settings.routes import bp as settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dash_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(tx_bp)
    app.register_blueprint(transfers_bp)
    app.register_blueprint(debts_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(unc_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(settings_bp)

    @app.route("/")
    def index():
        if session.get("user_id"):
            return redirect(url_for("dashboard.index"))
        from app.models import User
        if User.query.count() == 0:
            return redirect(url_for("auth.setup"))
        return redirect(url_for("auth.login"))

    @app.context_processor
    def inject_user():
        from flask import session as _s
        return {"current_user_id": _s.get("user_id"), "current_username": _s.get("username")}

    with app.app_context():
        db.create_all()
        seed_data()

    return app
