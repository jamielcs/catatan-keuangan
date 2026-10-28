from functools import wraps
from flask import session, redirect, url_for, flash, request
from extensions import db
from app.models import AuditLog, Transaction


def rupiah(value):
    try:
        v = int(value or 0)
    except Exception:
        v = 0
    sign = "-" if v < 0 else ""
    v = abs(v)
    s = f"{v:,}".replace(",", ".")
    return f"{sign}Rp {s}"


def parse_amount(raw):
    if raw is None:
        return None
    s = str(raw).strip().replace("Rp", "").replace(".", "").replace(",", "").replace(" ", "")
    if s == "" or s == "-":
        return None
    try:
        v = int(s)
    except Exception:
        return None
    return v


def parse_date(raw, default=None):
    from datetime import datetime
    if not raw:
        return default
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return default


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def audit(action, details=""):
    try:
        log = AuditLog(user_id=session.get("user_id"), action=action, details=str(details)[:2000])
        db.session.add(log)
        # caller commits; if standalone, commit here handled by caller usually
    except Exception:
        pass


def add_transaction(account, type_, signed_amount, description="", notes="", category_id=None,
                    person_id=None, transfer_id=None, date=None, reference_type="", reference_id=None):
    from app.models import now_jkt
    tx = Transaction(
        account_id=account.id,
        type=type_,
        amount=abs(int(signed_amount)),
        signed_amount=int(signed_amount),
        description=description or "",
        notes=notes or "",
        category_id=category_id,
        person_id=person_id,
        transfer_id=transfer_id,
        date=date or now_jkt(),
        affects_balance=True,
        status="active",
        reference_type=reference_type or "",
        reference_id=reference_id,
    )
    account.balance = int(account.balance or 0) + int(signed_amount)
    db.session.add(tx)
    db.session.flush()
    return tx


def cancel_transaction(tx, reason=""):
    """Reverse a transaction: create reversal, mark original cancelled, restore balance."""
    from app.models import now_jkt
    if tx.status == "cancelled":
        return None
    account = tx.account
    reversal = Transaction(
        account_id=tx.account_id,
        type="koreksi",
        amount=tx.amount,
        signed_amount=-tx.signed_amount,
        description=f"Pembalikan: {tx.description} {reason}".strip(),
        notes=reason or "",
        category_id=tx.category_id,
        person_id=tx.person_id,
        date=now_jkt(),
        affects_balance=True,
        status="active",
        is_reversal=True,
        reversal_of_id=tx.id,
        reference_type=tx.reference_type or "",
        reference_id=tx.reference_id,
    )
    account.balance = int(account.balance or 0) - int(tx.signed_amount)
    tx.status = "cancelled"
    db.session.add(reversal)
    db.session.flush()
    audit("cancel_transaction", f"tx#{tx.id} dibatalkan: {reason}")
    return reversal
