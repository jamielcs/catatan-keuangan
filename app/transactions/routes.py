from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from app.models import Account, Transaction, ExpenseCategory, Person, now_jkt
from app.utils import login_required, parse_amount, parse_date, add_transaction, audit, cancel_transaction

bp = Blueprint("transactions", __name__, url_prefix="/transactions")


@bp.route("/")
@login_required
def index():
    # Riwayat transaksi central
    q = Transaction.query.order_by(Transaction.date.desc(), Transaction.id.desc())
    # filters
    acc_id = request.args.get("account_id", type=int)
    type_ = request.args.get("type", "")
    cat_id = request.args.get("category_id", type=int)
    person_id = request.args.get("person_id", type=int)
    keyword = (request.args.get("q") or "").strip()
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    if acc_id:
        q = q.filter(Transaction.account_id == acc_id)
    if type_:
        q = q.filter(Transaction.type == type_)
    if cat_id:
        q = q.filter(Transaction.category_id == cat_id)
    if person_id:
        q = q.filter(Transaction.person_id == person_id)
    if keyword:
        q = q.filter(Transaction.description.ilike(f"%{keyword}%"))
    if date_from:
        d = parse_date(date_from)
        if d:
            q = q.filter(Transaction.date >= d)
    if date_to:
        d = parse_date(date_to)
        if d:
            from datetime import timedelta
            q = q.filter(Transaction.date <= d + timedelta(days=1) - timedelta(seconds=1))
    txs = q.limit(500).all()
    return render_template("transactions/history.html", transactions=txs,
                           accounts=Account.query.order_by(Account.name).all(),
                           categories=ExpenseCategory.query.order_by(ExpenseCategory.name).all(),
                           people=Person.query.order_by(Person.name).all())


@bp.route("/tambah", methods=["GET", "POST"])
@login_required
def tambah():
    accounts = Account.query.filter_by(is_active=True).order_by(Account.id).all()
    if request.method == "POST":
        acc = Account.query.get(request.form.get("account_id", type=int))
        amount = parse_amount(request.form.get("amount"))
        desc = (request.form.get("description") or "").strip()
        if not acc:
            flash("Rekening wajib dipilih.", "danger")
        elif amount is None or amount <= 0:
            flash("Nominal harus lebih besar dari nol.", "danger")
        else:
            add_transaction(acc, "pemasukan", amount, description=desc or "Tambah saldo",
                            date=parse_date(request.form.get("date"), now_jkt()),
                            notes=request.form.get("notes", ""))
            db.session.commit()
            flash("Saldo berhasil ditambahkan.", "success")
            return redirect(url_for("dashboard.index"))
    return render_template("transactions/add.html", accounts=accounts, mode="tambah")


@bp.route("/kurangi", methods=["GET", "POST"])
@login_required
def kurangi():
    accounts = Account.query.filter_by(is_active=True).order_by(Account.id).all()
    if request.method == "POST":
        acc = Account.query.get(request.form.get("account_id", type=int))
        amount = parse_amount(request.form.get("amount"))
        desc = (request.form.get("description") or "").strip()
        if not acc:
            flash("Rekening wajib dipilih.", "danger")
        elif amount is None or amount <= 0:
            flash("Nominal harus lebih besar dari nol.", "danger")
        elif amount > (acc.balance or 0):
            flash("Saldo tidak mencukupi. Pengurangan ditolak.", "danger")
        else:
            add_transaction(acc, "pengeluaran", -amount, description=desc or "Kurangi saldo",
                            date=parse_date(request.form.get("date"), now_jkt()),
                            notes=request.form.get("notes", ""))
            db.session.commit()
            flash("Saldo berhasil dikurangi.", "success")
            return redirect(url_for("dashboard.index"))
    return render_template("transactions/add.html", accounts=accounts, mode="kurangi")


@bp.route("/penyesuaian", methods=["GET", "POST"])
@login_required
def penyesuaian():
    accounts = Account.query.filter_by(is_active=True).order_by(Account.id).all()
    if request.method == "POST":
        acc = Account.query.get(request.form.get("account_id", type=int))
        target = parse_amount(request.form.get("target_balance"))
        reason = (request.form.get("reason") or "").strip()
        if not acc:
            flash("Rekening wajib dipilih.", "danger")
        elif target is None or target < 0:
            flash("Saldo target tidak valid.", "danger")
        elif not reason:
            flash("Alasan penyesuaian wajib diisi.", "danger")
        else:
            delta = target - int(acc.balance or 0)
            if delta == 0:
                flash("Saldo sudah sama dengan target, tidak ada perubahan.", "info")
            else:
                add_transaction(acc, "penyesuaian", delta, description=f"Penyesuaian saldo: {reason}",
                                date=parse_date(request.form.get("date"), now_jkt()))
                audit("penyesuaian", f"{acc.name} delta {delta} target {target} alasan {reason}")
                db.session.commit()
                flash("Penyesuaian saldo berhasil.", "success")
            return redirect(url_for("accounts.index"))
    return render_template("transactions/adjust.html", accounts=accounts)


@bp.route("/<int:tx_id>/cancel", methods=["POST"])
@login_required
def cancel(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    reason = (request.form.get("reason") or "Pembatalan manual").strip()
    if tx.status == "cancelled":
        flash("Transaksi sudah dibatalkan.", "warning")
    else:
        cancel_transaction(tx, reason)
        audit("cancel_transaction_route", f"tx#{tx.id} {reason}")
        db.session.commit()
        flash("Transaksi dibatalkan dan saldo dikembalikan via pembalikan.", "success")
    return redirect(request.referrer or url_for("transactions.index"))
