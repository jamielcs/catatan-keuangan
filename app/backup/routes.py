import os, sqlite3, shutil
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from extensions import db
from app.models import now_jkt
from app.utils import login_required, audit
from config import BASE_DIR

bp = Blueprint("backup", __name__, url_prefix="/backup")

BACKUP_DIR = os.path.join(BASE_DIR, "backups")
DB_PATH = os.path.join(BASE_DIR, "instance", "catatan_aprilcell.db")
REQUIRED_TABLES = {"users", "accounts", "transactions", "transfers", "people", "debts", "expense_categories"}


def list_backups():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    files = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.endswith(".db"):
            p = os.path.join(BACKUP_DIR, f)
            files.append({"name": f, "size": os.path.getsize(p), "path": p})
    return files


def do_backup(prefix="backup"):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name = f"{prefix}-{now_jkt().strftime('%Y%m%d-%H%M%S')}.db"
    dest = os.path.join(BACKUP_DIR, name)
    # Use sqlite backup API on the live connection if file exists, else create_all copy
    src_path = current_app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
    if os.path.exists(src_path):
        src = sqlite3.connect(src_path)
        dst = sqlite3.connect(dest)
        with dst:
            src.backup(dst)
        dst.close(); src.close()
    else:
        # fallback empty
        db.session.commit()
        shutil.copyfile(src_path, dest) if os.path.exists(src_path) else None
    audit("backup", f"Backup dibuat {name}")
    db.session.commit()
    return name


def validate_backup(path):
    try:
        con = sqlite3.connect(path)
        cur = con.cursor()
        cur.execute("PRAGMA integrity_check")
        res = cur.fetchone()
        if not res or res[0] != "ok":
            con.close(); return False, "Integrity check gagal"
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        con.close()
        if not REQUIRED_TABLES.issubset(tables):
            return False, f"Tabel wajib tidak lengkap: {REQUIRED_TABLES - tables}"
        return True, "OK"
    except Exception as e:
        return False, str(e)


@bp.route("/")
@login_required
def index():
    return render_template("backup/index.html", backups=list_backups())


@bp.route("/create", methods=["POST"])
@login_required
def create():
    try:
        name = do_backup()
        flash(f"Backup berhasil dibuat: {name}", "success")
    except Exception as e:
        flash(f"Backup gagal: {e}", "danger")
    return redirect(url_for("backup.index"))


@bp.route("/download/<path:filename>")
@login_required
def download(filename):
    safe = os.path.basename(filename)
    p = os.path.join(BACKUP_DIR, safe)
    if not os.path.exists(p):
        flash("File backup tidak ditemukan.", "danger"); return redirect(url_for("backup.index"))
    return send_file(p, as_attachment=True, download_name=safe)


@bp.route("/restore", methods=["POST"])
@login_required
def restore():
    filename = os.path.basename(request.form.get("filename", ""))
    p = os.path.join(BACKUP_DIR, filename)
    if not filename or not os.path.exists(p):
        flash("File backup tidak ditemukan.", "danger"); return redirect(url_for("backup.index"))
    ok, msg = validate_backup(p)
    if not ok:
        flash(f"Restore dibatalkan, file tidak valid: {msg}", "danger"); return redirect(url_for("backup.index"))
    try:
        # backup current first
        pre = do_backup(prefix="pre-restore")
        src_path = current_app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
        db.session.remove()
        db.engine.dispose()
        shutil.copyfile(p, src_path)
        audit_msg = f"Restore dari {filename}, pre-backup {pre}"
        # after restore, engine reconnects lazily; add audit in new session (best effort)
        try:
            audit("restore", audit_msg); db.session.commit()
        except Exception:
            db.session.rollback()
        flash(f"Restore berhasil dari {filename}. Backup sebelum restore: {pre}", "success")
    except Exception as e:
        flash(f"Restore gagal: {e}", "danger")
    return redirect(url_for("backup.index"))
