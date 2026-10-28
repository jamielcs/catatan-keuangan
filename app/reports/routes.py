import csv, io
from datetime import timedelta
from flask import Blueprint, render_template, request, Response
from sqlalchemy import func
from extensions import db
from app.models import Account, Transaction, ExpenseCategory, Person, now_jkt
from app.utils import login_required, parse_date

bp = Blueprint("reports", __name__, url_prefix="/reports")

INCOME_TYPES = ["pemasukan"]  # external only; saldo_awal counted separately in opening balance reconstruction
EXPENSE_TYPES = ["pengeluaran"]


def period_range(kind, custom_from=None, custom_to=None):
    now = now_jkt()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if kind == "harian":
        return today, today + timedelta(days=1) - timedelta(seconds=1)
    if kind == "mingguan":
        monday = today - timedelta(days=today.weekday())
        return monday, monday + timedelta(days=7) - timedelta(seconds=1)
    if kind == "bulanan":
        start = today.replace(day=1)
        nxt = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
        return start, nxt - timedelta(seconds=1)
    if kind == "custom" and custom_from and custom_to:
        return custom_from, custom_to + timedelta(days=1) - timedelta(seconds=1)
    # default bulanan
    start = today.replace(day=1)
    nxt = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    return start, nxt - timedelta(seconds=1)


def build_report(kind, acc_id=None, cat_id=None):
    cf = parse_date(request.args.get("date_from")) if request.args.get("date_from") else None
    ct = parse_date(request.args.get("date_to")) if request.args.get("date_to") else None
    start, end = period_range(kind, cf, ct)
    # saldo awal periode = current balance - sum signed after start? reconstruct: sum signed before start
    q_open = db.session.query(func.coalesce(func.sum(Transaction.signed_amount), 0)).filter(
        Transaction.status == "active", Transaction.affects_balance == True, Transaction.date < start)
    if acc_id:
        q_open = q_open.filter(Transaction.account_id == acc_id)
    saldo_awal = int(q_open.scalar() or 0)
    base = Transaction.query.filter(Transaction.status == "active", Transaction.date >= start, Transaction.date <= end)
    if acc_id:
        base = base.filter(Transaction.account_id == acc_id)
    if cat_id:
        base = base.filter(Transaction.category_id == cat_id)
    txs = base.order_by(Transaction.date.asc()).all()
    pemasukan = sum(t.amount for t in txs if t.type in INCOME_TYPES)
    pengeluaran = sum(t.amount for t in txs if t.type in EXPENSE_TYPES)
    transfer_total = sum(t.amount for t in txs if t.type == "transfer_masuk")
    perubahan = sum(t.signed_amount for t in txs if t.affects_balance)
    saldo_akhir = saldo_awal + perubahan
    by_category, by_person, by_account = {}, {}, {}
    for t in txs:
        if t.type in EXPENSE_TYPES:
            k = t.category.name if t.category else "-"
            by_category[k] = by_category.get(k, 0) + t.amount
            kp = t.person.name if t.person else "-"
            by_person[kp] = by_person.get(kp, 0) + t.amount
        if t.type in INCOME_TYPES:
            ka = t.account.short_name if t.account else "-"
            by_account[ka] = by_account.get(ka, 0) + t.amount
    return dict(start=start, end=end, saldo_awal=saldo_awal, pemasukan=pemasukan, pengeluaran=pengeluaran,
                transfer_total=transfer_total, perubahan=perubahan, saldo_akhir=saldo_akhir,
                transactions=txs, by_category=by_category, by_person=by_person, by_account=by_account)


@bp.route("/")
@login_required
def index():
    kind = request.args.get("period", "bulanan")
    if kind not in ("harian", "mingguan", "bulanan", "custom"):
        kind = "bulanan"
    acc_id = request.args.get("account_id", type=int)
    cat_id = request.args.get("category_id", type=int)
    rep = build_report(kind, acc_id, cat_id)
    return render_template("reports/index.html", rep=rep, period=kind,
                           accounts=Account.query.order_by(Account.name).all(),
                           categories=ExpenseCategory.query.order_by(ExpenseCategory.name).all())


@bp.route("/print")
@login_required
def print_view():
    kind = request.args.get("period", "bulanan")
    rep = build_report(kind, request.args.get("account_id", type=int), request.args.get("category_id", type=int))
    return render_template("reports/print.html", rep=rep, period=kind)


@bp.route("/export.csv")
@login_required
def export_csv():
    kind = request.args.get("period", "bulanan")
    rep = build_report(kind, request.args.get("account_id", type=int), request.args.get("category_id", type=int))
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Tanggal", "Jenis", "Rekening", "Nominal", "Signed", "Keterangan", "Status"])
    for t in rep["transactions"]:
        w.writerow([t.date, t.type, t.account.short_name if t.account else "", t.amount, t.signed_amount, t.description, t.status])
    resp = Response(out.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = f"attachment; filename=laporan-{kind}.csv"
    return resp
