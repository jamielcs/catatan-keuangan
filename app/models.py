from datetime import datetime, timezone, timedelta
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

JKT = timezone(timedelta(hours=7))


def now_jkt():
    return datetime.now(JKT).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=now_jkt)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Account(db.Model):
    __tablename__ = "accounts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    short_name = db.Column(db.String(50), nullable=False)
    account_type = db.Column(db.String(50), default="bank")
    balance = db.Column(db.Integer, default=0, nullable=False)  # rupiah int
    initial_balance = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_jkt)
    transactions = db.relationship("Transaction", backref="account", lazy=True)


class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    type = db.Column(db.String(40), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)  # abs
    signed_amount = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    notes = db.Column(db.Text, default="")
    category_id = db.Column(db.Integer, db.ForeignKey("expense_categories.id"), nullable=True, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=True, index=True)
    transfer_id = db.Column(db.Integer, db.ForeignKey("transfers.id"), nullable=True, index=True)
    status = db.Column(db.String(20), default="active", index=True)  # active/cancelled
    affects_balance = db.Column(db.Boolean, default=True)
    is_reversal = db.Column(db.Boolean, default=False)
    reversal_of_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    reference_type = db.Column(db.String(50), default="")
    reference_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=now_jkt)
    category = db.relationship("ExpenseCategory", lazy=True)
    person = db.relationship("Person", lazy=True)


class Transfer(db.Model):
    __tablename__ = "transfers"
    id = db.Column(db.Integer, primary_key=True)
    from_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    to_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=now_jkt)
    from_account = db.relationship("Account", foreign_keys=[from_account_id])
    to_account = db.relationship("Account", foreign_keys=[to_account_id])


class Person(db.Model):
    __tablename__ = "people"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    contact = db.Column(db.String(120), default="")
    notes = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_jkt)


class Debt(db.Model):
    __tablename__ = "debts"
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=False, index=True)
    direction = db.Column(db.String(20), nullable=False, index=True)  # piutang / utang
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    principal = db.Column(db.Integer, nullable=False)
    paid_amount = db.Column(db.Integer, default=0)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    status = db.Column(db.String(20), default="aktif")  # aktif / lunas
    created_at = db.Column(db.DateTime, default=now_jkt)
    person = db.relationship("Person", backref="debts")
    account = db.relationship("Account")

    @property
    def remaining(self):
        return self.principal - (self.paid_amount or 0)


class DebtPayment(db.Model):
    __tablename__ = "debt_payments"
    id = db.Column(db.Integer, primary_key=True)
    debt_id = db.Column(db.Integer, db.ForeignKey("debts.id"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    amount = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=now_jkt)
    debt = db.relationship("Debt", backref="payments")
    account = db.relationship("Account")


class ExpenseCategory(db.Model):
    __tablename__ = "expense_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_jkt)


class Expense(db.Model):
    __tablename__ = "expenses"
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("expense_categories.id"), nullable=True, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=True, index=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    amount = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=now_jkt)
    account = db.relationship("Account")
    category = db.relationship("ExpenseCategory")
    person = db.relationship("Person")


class UncollectedIncome(db.Model):
    __tablename__ = "uncollected_income"
    id = db.Column(db.Integer, primary_key=True)
    source_name = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    received_amount = db.Column(db.Integer, default=0)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    status = db.Column(db.String(30), default="belum_diambil")  # belum_diambil/diambil_sebagian/sudah_diambil
    created_at = db.Column(db.DateTime, default=now_jkt)

    @property
    def remaining(self):
        return self.amount - (self.received_amount or 0)

    def refresh_status(self):
        if self.remaining <= 0:
            self.status = "sudah_diambil"
        elif (self.received_amount or 0) > 0:
            self.status = "diambil_sebagian"
        else:
            self.status = "belum_diambil"


class UncollectedIncomePayment(db.Model):
    __tablename__ = "uncollected_income_payments"
    id = db.Column(db.Integer, primary_key=True)
    uncollected_id = db.Column(db.Integer, db.ForeignKey("uncollected_income.id"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=now_jkt)
    uncollected = db.relationship("UncollectedIncome", backref="payments")
    account = db.relationship("Account")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    details = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=now_jkt, index=True)
    user = db.relationship("User")


class AppSetting(db.Model):
    __tablename__ = "app_settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default="")
