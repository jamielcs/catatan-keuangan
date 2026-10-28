from datetime import timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from app.models import User, now_jkt
from app.utils import audit

bp = Blueprint("auth", __name__)


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    if User.query.count() > 0:
        flash("Setup sudah dikunci. Aplikasi sudah memiliki administrator.", "warning")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        if len(username) < 3:
            flash("Username minimal 3 karakter.", "danger")
        elif len(password) < 6:
            flash("Password minimal 6 karakter.", "danger")
        elif password != confirm:
            flash("Konfirmasi password tidak sama.", "danger")
        else:
            u = User(username=username)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            audit("setup_admin", f"Admin {username} dibuat")
            db.session.commit()
            flash("Akun administrator berhasil dibuat. Silakan login.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/setup.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if User.query.count() == 0:
        return redirect(url_for("auth.setup"))
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        now = now_jkt()
        if user and user.locked_until and user.locked_until > now:
            flash("Akun terkunci sementara karena terlalu banyak percobaan gagal. Coba lagi nanti.", "danger")
            return render_template("auth/login.html")
        if user and user.check_password(password):
            user.failed_attempts = 0
            user.locked_until = None
            db.session.commit()
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            session.permanent = True
            audit("login", f"{username} login")
            db.session.commit()
            nxt = request.args.get("next") or url_for("dashboard.index")
            if not nxt.startswith("/"):
                nxt = url_for("dashboard.index")
            return redirect(nxt)
        # failed
        if user:
            user.failed_attempts = (user.failed_attempts or 0) + 1
            if user.failed_attempts >= 5:
                user.locked_until = now + timedelta(minutes=5)
                user.failed_attempts = 0
            db.session.commit()
        flash("Username atau password salah.", "danger")
    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    if session.get("user_id"):
        audit("logout", f"{session.get('username')} logout")
        db.session.commit()
    session.clear()
    flash("Anda sudah logout.", "success")
    return redirect(url_for("auth.login"))
