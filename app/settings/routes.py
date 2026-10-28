from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from app.models import User, ExpenseCategory, AuditLog, Person
from app.utils import login_required, audit

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    user = User.query.get(session.get("user_id"))
    if request.method == "POST" and request.form.get("action") == "change_password":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not user.check_password(current):
            flash("Password saat ini salah.", "danger")
        elif len(new) < 6:
            flash("Password baru minimal 6 karakter.", "danger")
        elif new != confirm:
            flash("Konfirmasi password baru tidak sama.", "danger")
        else:
            user.set_password(new)
            audit("change_password", f"User {user.username} ganti password")
            db.session.commit()
            flash("Password berhasil diubah.", "success")
            return redirect(url_for("settings.index"))
    categories = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    logs = AuditLog.query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(100).all()
    people = Person.query.order_by(Person.name).all()
    return render_template("settings/index.html", user=user, categories=categories, logs=logs, people=people)


@bp.route("/categories/create", methods=["POST"])
@login_required
def create_category():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Nama kategori wajib diisi.", "danger")
    elif ExpenseCategory.query.filter_by(name=name).first():
        flash("Kategori sudah ada.", "danger")
    else:
        db.session.add(ExpenseCategory(name=name))
        audit("create_category", name); db.session.commit()
        flash("Kategori ditambahkan.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/categories/<int:cid>/edit", methods=["POST"])
@login_required
def edit_category(cid):
    c = ExpenseCategory.query.get_or_404(cid)
    c.name = (request.form.get("name") or c.name).strip()
    db.session.commit(); flash("Kategori diperbarui.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/categories/<int:cid>/deactivate", methods=["POST"])
@login_required
def deactivate_category(cid):
    c = ExpenseCategory.query.get_or_404(cid)
    c.is_active = False
    audit("deactivate_category", c.name); db.session.commit()
    flash("Kategori dinonaktifkan.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/categories/<int:cid>/activate", methods=["POST"])
@login_required
def activate_category(cid):
    c = ExpenseCategory.query.get_or_404(cid)
    c.is_active = True; db.session.commit()
    flash("Kategori diaktifkan.", "success")
    return redirect(url_for("settings.index"))
