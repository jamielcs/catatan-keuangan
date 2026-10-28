from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from app.models import Account, Person, Debt, DebtPayment, now_jkt
from app.utils import login_required, parse_amount, parse_date, add_transaction, audit

bp = Blueprint("debts", __name__, url_prefix="/debts")


@bp.route("/")
@login_required
def index():
    person_id = request.args.get("person_id", type=int)
    q = Debt.query.order_by(Debt.date.desc(), Debt.id.desc())
    if person_id:
        q = q.filter_by(person_id=person_id)
    debts = q.all()
    piutang_total = sum(d.remaining for d in Debt.query.filter_by(direction="piutang", status="aktif").all())
    utang_total = sum(d.remaining for d in Debt.query.filter_by(direction="utang", status="aktif").all())
    return render_template("debts/index.html", debts=debts, people=Person.query.filter_by(is_active=True).order_by(Person.name).all(),
                           accounts=Account.query.filter_by(is_active=True).all(), piutang_total=piutang_total, utang_total=utang_total)


@bp.route("/people/create", methods=["POST"])
@login_required
def create_person():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Nama orang wajib diisi.", "danger")
    elif Person.query.filter_by(name=name).first():
        flash("Nama orang sudah ada.", "danger")
    else:
        p = Person(name=name, contact=request.form.get("contact", ""), notes=request.form.get("notes", ""))
        db.session.add(p); db.session.commit()
        flash("Orang berhasil ditambahkan.", "success")
    return redirect(url_for("debts.index"))


@bp.route("/people/<int:pid>/edit", methods=["POST"])
@login_required
def edit_person(pid):
    p = Person.query.get_or_404(pid)
    p.name = (request.form.get("name") or p.name).strip()
    p.contact = request.form.get("contact", p.contact or "")
    p.notes = request.form.get("notes", p.notes or "")
    db.session.commit()
    flash("Data orang diperbarui.", "success")
    return redirect(url_for("debts.index"))


@bp.route("/create", methods=["POST"])
@login_required
def create():
    person_id = request.form.get("person_id", type=int)
    direction = request.form.get("direction", "piutang")
    account_id = request.form.get("account_id", type=int)
    amount = parse_amount(request.form.get("amount"))
    desc = (request.form.get("description") or "").strip()
    person = Person.query.get(person_id) if person_id else None
    account = Account.query.get(account_id) if account_id else None
    if not person:
        flash("Orang wajib dipilih.", "danger"); return redirect(url_for("debts.index"))
    if direction not in ("piutang", "utang"):
        flash("Arah tidak valid.", "danger"); return redirect(url_for("debts.index"))
    if amount is None or amount <= 0:
        flash("Nominal harus lebih besar dari nol.", "danger"); return redirect(url_for("debts.index"))
    if direction == "piutang":
        if not account:
            flash("Rekening sumber wajib dipilih untuk piutang.", "danger"); return redirect(url_for("debts.index"))
        if amount > (account.balance or 0):
            flash("Saldo rekening tidak mencukupi untuk meminjamkan.", "danger"); return redirect(url_for("debts.index"))
    # utang: receiving money increases balance if account given; allow no account? require account
    if direction == "utang" and not account:
        flash("Rekening tujuan wajib dipilih untuk utang.", "danger"); return redirect(url_for("debts.index"))
    try:
        debt = Debt(person_id=person.id, direction=direction, account_id=account.id if account else None,
                    principal=amount, paid_amount=0, description=desc,
                    date=parse_date(request.form.get("date"), now_jkt()))
        db.session.add(debt); db.session.flush()
        if direction == "piutang":
            add_transaction(account, "pinjaman_keluar", -amount, description=desc or f"Pinjaman ke {person.name}",
                            person_id=person.id, date=debt.date, reference_type="debt", reference_id=debt.id)
        else:
            add_transaction(account, "utang_masuk", amount, description=desc or f"Utang dari {person.name}",
                            person_id=person.id, date=debt.date, reference_type="debt", reference_id=debt.id)
        db.session.commit()
        flash("Catatan utang/piutang berhasil dibuat.", "success")
    except Exception as e:
        db.session.rollback(); flash(f"Gagal: {e}", "danger")
    return redirect(url_for("debts.index"))


@bp.route("/<int:debt_id>/pay", methods=["POST"])
@login_required
def pay(debt_id):
    debt = Debt.query.get_or_404(debt_id)
    amount = parse_amount(request.form.get("amount"))
    account_id = request.form.get("account_id", type=int)
    account = Account.query.get(account_id) if account_id else (Account.query.get(debt.account_id) if debt.account_id else None)
    if amount is None or amount <= 0:
        flash("Nominal pembayaran harus lebih besar dari nol.", "danger"); return redirect(url_for("debts.index"))
    if amount > debt.remaining:
        flash("Pembayaran melebihi sisa.", "danger"); return redirect(url_for("debts.index"))
    if not account:
        flash("Rekening wajib dipilih untuk pembayaran.", "danger"); return redirect(url_for("debts.index"))
    if debt.direction == "utang" and amount > (account.balance or 0):
        flash("Saldo tidak mencukupi untuk membayar utang.", "danger"); return redirect(url_for("debts.index"))
    try:
        if debt.direction == "piutang":
            tx = add_transaction(account, "pembayaran_piutang", amount, description=f"Pembayaran piutang {debt.person.name}",
                                 person_id=debt.person_id, reference_type="debt", reference_id=debt.id)
        else:
            tx = add_transaction(account, "pembayaran_utang", -amount, description=f"Pembayaran utang ke {debt.person.name}",
                                 person_id=debt.person_id, reference_type="debt", reference_id=debt.id)
        paym = DebtPayment(debt_id=debt.id, account_id=account.id, amount=amount, transaction_id=tx.id,
                           description=request.form.get("description", ""))
        db.session.add(paym)
        debt.paid_amount = (debt.paid_amount or 0) + amount
        if debt.remaining <= 0:
            debt.status = "lunas"
        db.session.commit()
        flash("Pembayaran berhasil dicatat.", "success")
    except Exception as e:
        db.session.rollback(); flash(f"Gagal: {e}", "danger")
    return redirect(url_for("debts.index"))


@bp.route("/<int:debt_id>")
@login_required
def detail(debt_id):
    debt = Debt.query.get_or_404(debt_id)
    return render_template("debts/detail.html", debt=debt, accounts=Account.query.filter_by(is_active=True).all())
