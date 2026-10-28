from datetime import timedelta, date
from flask import Blueprint, render_template
from sqlalchemy import func
from extensions import db
from app.models import Account, Transaction, Debt, UncollectedIncome, now_jkt
from app.utils import login_required

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _sum_tx(types, start, end):
    q = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.type.in_(types), Transaction.status == "active",
        Transaction.date >= start, Transaction.date <= end)
    return int(q.scalar() or 0)


@bp.route("/")
@login_required
def index():
    now = now_jkt()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1) - timedelta(seconds=1)
    monday = today_start - timedelta(days=today_start.weekday())
    sunday_end = monday + timedelta(days=7) - timedelta(seconds=1)
    month_start = today_start.replace(day=1)
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    month_end = next_month - timedelta(seconds=1)

    accounts = Account.query.filter_by(is_active=True).order_by(Account.id).all()
    total_saldo = sum(a.balance or 0 for a in accounts)
    all_accounts = Account.query.order_by(Account.id).all()

    pemasukan_bulan = _sum_tx(["pemasukan"], month_start, month_end)
    pengeluaran_bulan = _sum_tx(["pengeluaran"], month_start, month_end)
    # pengeluaran includes expenses which are type pengeluaran; good

    piutang = sum(d.remaining for d in Debt.query.filter_by(direction="piutang", status="aktif").all())
    utang = sum(d.remaining for d in Debt.query.filter_by(direction="utang", status="aktif").all())
    belum_diambil = sum(u.remaining for u in UncollectedIncome.query.filter(UncollectedIncome.status != "sudah_diambil").all())

    recent = Transaction.query.filter_by(status="active").order_by(Transaction.date.desc(), Transaction.id.desc()).limit(10).all()

    summary = {
        "harian": {"pemasukan": _sum_tx(["pemasukan"], today_start, today_end),
                   "pengeluaran": _sum_tx(["pengeluaran"], today_start, today_end)},
        "mingguan": {"pemasukan": _sum_tx(["pemasukan"], monday, sunday_end),
                     "pengeluaran": _sum_tx(["pengeluaran"], monday, sunday_end)},
        "bulanan": {"pemasukan": pemasukan_bulan, "pengeluaran": pengeluaran_bulan},
    }
    # chart data last 6 months labels
    labels, inc_data, exp_data = [], [], []
    y, m = now.year, now.month
    months = []
    for i in range(5, -1, -1):
        mm = m - i
        yy = y
        while mm <= 0:
            mm += 12; yy -= 1
        months.append((yy, mm))
    for yy, mm in months:
        start = now.replace(year=yy, month=mm, day=1, hour=0, minute=0, second=0, microsecond=0)
        if mm == 12:
            nxt = start.replace(year=yy + 1, month=1)
        else:
            nxt = start.replace(month=mm + 1)
        end = nxt - timedelta(seconds=1)
        labels.append(f"{mm:02d}/{yy}")
        inc_data.append(_sum_tx(["pemasukan"], start, end))
        exp_data.append(_sum_tx(["pengeluaran"], start, end))

    return render_template("dashboard/index.html", accounts=all_accounts, total_saldo=total_saldo,
                           pemasukan_bulan=pemasukan_bulan, pengeluaran_bulan=pengeluaran_bulan,
                           piutang=piutang, utang=utang, belum_diambil=belum_diambil,
                           recent=recent, summary=summary, chart_labels=labels,
                           chart_income=inc_data, chart_expense=exp_data)
