from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import func
from extensions import db
from app.models import Account, Expense, ExpenseCategory, Person, now_jkt
from app.utils import login_required, parse_amount, parse_date, add_transaction, audit, cancel_transaction

bp = Blueprint("expenses", __name__, url_prefix="/expenses")


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    accounts = Account.query.filter_by(is_active=True).order_by(Account.id).all()
    categories = ExpenseCategory.query.filter_by(is_active=True).order_by(ExpenseCategory.name).all()
    people = Person.query.filter_by(is_active=True).order_by(Person.name).all()
    if request.method == "POST":
        acc = Account.query.get(request.form.get("account_id", type=int))
        amount = parse_amount(request.form.get("amount"))
        if not acc:
            flash("Rekening wajib dipilih.", "danger")
        elif amount is None or amount <= 0:
            flash("Nominal harus lebih besar dari nol.", "danger")
        elif amount > (acc.balance or 0):
            flash("Saldo tidak mencukupi untuk pengeluaran ini.", "danger")
        else:
            cat_id = request.form.get("category_id", type=int)
            person_id = request.form.get("person_id", type=int)
            exp = Expense(account_id=acc.id, category_id=cat_id, person_id=person_id,
                          amount=amount, description=(request.form.get("description") or "").strip(),
                          notes=request.form.get("notes", ""), date=parse_date(request.form.get("date"), now_jkt()))
            db.session.add(exp); db.session.flush()
            tx = add_transaction(acc, "pengeluaran", -amount, description=exp.description or "Pengeluaran",
                                 category_id=cat_id, person_id=person_id, date=exp.date,
                                 reference_type="expense", reference_id=exp.id)
            exp.transaction_id = tx.id
            db.session.commit()
            flash("Pengeluaran berhasil dicatat.", "success")
            return redirect(url_for("expenses.index"))
    q = Expense.query.filter_by(status="active").order_by(Expense.date.desc(), Expense.id.desc())
    # filters
    if request.args.get("category_id", type=int):
        q = q.filter_by(category_id=request.args.get("category_id", type=int))
    if request.args.get("account_id", type=int):
        q = q.filter_by(account_id=request.args.get("account_id", type=int))
    if request.args.get("person_id", type=int):
        q = q.filter_by(person_id=request.args.get("person_id", type=int))
    kw = (request.args.get("q") or "").strip()
    if kw:
        q = q.filter(Expense.description.ilike(f"%{kw}%"))
    if request.args.get("date_from"):
        d = parse_date(request.args.get("date_from"))
        if d: q = q.filter(Expense.date >= d)
    if request.args.get("date_to"):
        d = parse_date(request.args.get("date_to"))
        if d:
            from datetime import timedelta
            q = q.filter(Expense.date <= d + timedelta(days=1) - timedelta(seconds=1))
    expenses = q.limit(500).all()
    total = sum(e.amount for e in expenses)
    by_category = {}
    by_person = {}
    by_day = {}
    for e in expenses:
        by_category[e.category.name if e.category else "-"] = by_category.get(e.category.name if e.category else "-", 0) + e.amount
        by_person[e.person.name if e.person else "-"] = by_person.get(e.person.name if e.person else "-", 0) + e.amount
        day = e.date.strftime("%Y-%m-%d") if e.date else "-"
        by_day[day] = by_day.get(day, 0) + e.amount
    return render_template("expenses/index.html", expenses=expenses, accounts=accounts, categories=categories,
                           people=people, total=total, by_category=by_category, by_person=by_person, by_day=by_day)


@bp.route("/<int:exp_id>/cancel", methods=["POST"])
@login_required
def cancel(exp_id):
    exp = Expense.query.get_or_404(exp_id)
    if exp.transaction_id:
        from app.models import Transaction
        tx = Transaction.query.get(exp.transaction_id)
        if tx and tx.status != "cancelled":
            cancel_transaction(tx, request.form.get("reason", "Pembatalan pengeluaran"))
    exp.status = "cancelled"
    audit("cancel_expense", f"expense#{exp.id}")
    db.session.commit()
    flash("Pengeluaran dibatalkan dan saldo dikembalikan.", "success")
    return redirect(url_for("expenses.index"))
