from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from app.models import Account, UncollectedIncome, UncollectedIncomePayment, now_jkt
from app.utils import login_required, parse_amount, parse_date, add_transaction

bp = Blueprint("uncollected", __name__, url_prefix="/uncollected")


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        source = (request.form.get("source_name") or "").strip()
        amount = parse_amount(request.form.get("amount"))
        if not source:
            flash("Nama sumber wajib diisi.", "danger")
        elif amount is None or amount <= 0:
            flash("Nominal harus lebih besar dari nol.", "danger")
        else:
            u = UncollectedIncome(source_name=source, amount=amount, received_amount=0,
                                  description=(request.form.get("description") or "").strip(),
                                  date=parse_date(request.form.get("date"), now_jkt()))
            u.refresh_status()
            db.session.add(u); db.session.commit()
            flash("Uang belum diambil berhasil dicatat.", "success")
            return redirect(url_for("uncollected.index"))
    items = UncollectedIncome.query.order_by(UncollectedIncome.date.desc(), UncollectedIncome.id.desc()).all()
    total_sisa = sum(i.remaining for i in items if i.status != "sudah_diambil")
    return render_template("uncollected/index.html", items=items, accounts=Account.query.filter_by(is_active=True).all(), total_sisa=total_sisa)


@bp.route("/<int:uid>/receive", methods=["POST"])
@login_required
def receive(uid):
    item = UncollectedIncome.query.get_or_404(uid)
    amount = parse_amount(request.form.get("amount"))
    acc = Account.query.get(request.form.get("account_id", type=int))
    if amount is None or amount <= 0:
        flash("Nominal penerimaan harus lebih besar dari nol.", "danger"); return redirect(url_for("uncollected.index"))
    if amount > item.remaining:
        flash("Penerimaan melebihi sisa.", "danger"); return redirect(url_for("uncollected.index"))
    if not acc:
        flash("Rekening tujuan wajib dipilih.", "danger"); return redirect(url_for("uncollected.index"))
    tx = add_transaction(acc, "pemasukan", amount, description=f"Penerimaan dari {item.source_name}",
                         reference_type="uncollected", reference_id=item.id,
                         date=parse_date(request.form.get("date"), now_jkt()))
    pay = UncollectedIncomePayment(uncollected_id=item.id, account_id=acc.id, amount=amount, transaction_id=tx.id,
                                   description=request.form.get("description", ""))
    db.session.add(pay)
    item.received_amount = (item.received_amount or 0) + amount
    item.refresh_status()
    db.session.commit()
    flash("Penerimaan berhasil dicatat dan saldo bertambah.", "success")
    return redirect(url_for("uncollected.index"))


@bp.route("/<int:uid>")
@login_required
def detail(uid):
    item = UncollectedIncome.query.get_or_404(uid)
    return render_template("uncollected/detail.html", item=item, accounts=Account.query.filter_by(is_active=True).all())
