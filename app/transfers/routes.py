from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from app.models import Account, Transfer, Transaction, now_jkt
from app.utils import login_required, parse_amount, parse_date, add_transaction

bp = Blueprint("transfers", __name__, url_prefix="/transfers")


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    accounts = Account.query.filter_by(is_active=True).order_by(Account.id).all()
    if request.method == "POST":
        from_id = request.form.get("from_account_id", type=int)
        to_id = request.form.get("to_account_id", type=int)
        amount = parse_amount(request.form.get("amount"))
        desc = (request.form.get("description") or "").strip()
        src = Account.query.get(from_id) if from_id else None
        dst = Account.query.get(to_id) if to_id else None
        if not src or not dst:
            flash("Rekening asal dan tujuan wajib dipilih.", "danger")
        elif src.id == dst.id:
            flash("Rekening asal dan tujuan tidak boleh sama.", "danger")
        elif amount is None or amount <= 0:
            flash("Nominal harus lebih besar dari nol.", "danger")
        elif amount > (src.balance or 0):
            flash("Saldo rekening asal tidak mencukupi.", "danger")
        else:
            try:
                tr = Transfer(from_account_id=src.id, to_account_id=dst.id, amount=amount,
                              description=desc, date=parse_date(request.form.get("date"), now_jkt()))
                db.session.add(tr); db.session.flush()
                d = tr.date
                add_transaction(src, "transfer_keluar", -amount, description=desc or f"Transfer ke {dst.name}",
                                transfer_id=tr.id, date=d, reference_type="transfer", reference_id=tr.id)
                add_transaction(dst, "transfer_masuk", amount, description=desc or f"Transfer dari {src.name}",
                                transfer_id=tr.id, date=d, reference_type="transfer", reference_id=tr.id)
                db.session.commit()
                flash("Transfer berhasil.", "success")
                return redirect(url_for("transfers.index"))
            except Exception as e:
                db.session.rollback()
                flash(f"Transfer gagal, dibatalkan: {e}", "danger")
    transfers = Transfer.query.order_by(Transfer.date.desc(), Transfer.id.desc()).limit(100).all()
    return render_template("transfers/index.html", accounts=accounts, transfers=transfers)
