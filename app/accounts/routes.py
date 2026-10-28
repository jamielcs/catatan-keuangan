from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from app.models import Account, Transaction, now_jkt
from app.utils import login_required, parse_amount, parse_date, add_transaction, audit

bp = Blueprint("accounts", __name__, url_prefix="/accounts")


@bp.route("/")
@login_required
def index():
    accounts = Account.query.order_by(Account.id).all()
    total = sum(a.balance or 0 for a in accounts if a.is_active)
    return render_template("accounts/index.html", accounts=accounts, total=total)


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        short = (request.form.get("short_name") or name).strip()
        typ = (request.form.get("account_type") or "bank").strip()
        if not name:
            flash("Nama rekening wajib diisi.", "danger")
        elif Account.query.filter_by(name=name).first():
            flash("Nama rekening sudah ada.", "danger")
        else:
            acc = Account(name=name, short_name=short, account_type=typ, balance=0)
            db.session.add(acc); db.session.commit()
            flash("Rekening berhasil ditambahkan.", "success")
            return redirect(url_for("accounts.index"))
    return render_template("accounts/form.html", account=None)


@bp.route("/<int:acc_id>/edit", methods=["GET", "POST"])
@login_required
def edit(acc_id):
    acc = Account.query.get_or_404(acc_id)
    if request.method == "POST":
        acc.name = (request.form.get("name") or acc.name).strip()
        acc.short_name = (request.form.get("short_name") or acc.short_name).strip()
        acc.account_type = (request.form.get("account_type") or acc.account_type).strip()
        db.session.commit()
        flash("Rekening diperbarui.", "success")
        return redirect(url_for("accounts.index"))
    return render_template("accounts/form.html", account=acc)


@bp.route("/<int:acc_id>/deactivate", methods=["POST"])
@login_required
def deactivate(acc_id):
    acc = Account.query.get_or_404(acc_id)
    acc.is_active = False
    audit("deactivate_account", f"Rekening {acc.name} dinonaktifkan")
    db.session.commit()
    flash("Rekening dinonaktifkan (tidak dihapus agar riwayat aman).", "success")
    return redirect(url_for("accounts.index"))


@bp.route("/<int:acc_id>/activate", methods=["POST"])
@login_required
def activate(acc_id):
    acc = Account.query.get_or_404(acc_id)
    acc.is_active = True
    db.session.commit()
    flash("Rekening diaktifkan kembali.", "success")
    return redirect(url_for("accounts.index"))


@bp.route("/<int:acc_id>/saldo-awal", methods=["GET", "POST"])
@login_required
def saldo_awal(acc_id):
    acc = Account.query.get_or_404(acc_id)
    if request.method == "POST":
        amount = parse_amount(request.form.get("amount"))
        if amount is None or amount < 0:
            flash("Nominal saldo awal harus angka 0 atau lebih.", "danger")
        else:
            # saldo awal as adjustment to reach amount if balance 0 typical; implement as pemasukan saldo_awal delta
            delta = amount - int(acc.balance or 0)
            if delta != 0:
                add_transaction(acc, "saldo_awal", delta, description="Saldo awal", date=parse_date(request.form.get("date"), now_jkt()))
                acc.initial_balance = amount
                audit("saldo_awal", f"{acc.name} saldo awal {amount}")
                db.session.commit()
            flash("Saldo awal berhasil disimpan.", "success")
            return redirect(url_for("accounts.index"))
    return render_template("accounts/saldo_awal.html", account=acc)


@bp.route("/<int:acc_id>")
@login_required
def detail(acc_id):
    acc = Account.query.get_or_404(acc_id)
    txs = Transaction.query.filter_by(account_id=acc.id).order_by(Transaction.date.desc(), Transaction.id.desc()).limit(100).all()
    return render_template("accounts/detail.html", account=acc, transactions=txs)
