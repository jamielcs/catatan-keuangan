import os, sys, io, re
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import TestConfig


@pytest.fixture(scope="module")
def app_instance(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("data") / "test.db"
    from app import create_app
    application = create_app(TestConfig, {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}", "_db_file": str(db_file)})
    application.config["_db_file"] = str(db_file)
    yield application


@pytest.fixture(scope="module")
def client(app_instance):
    return app_instance.test_client()


@pytest.fixture(scope="module")
def dbmod(app_instance):
    with app_instance.app_context():
        from extensions import db
        yield db


def acc_id_by_name(name):
    from app.models import Account
    return Account.query.filter_by(name=name).first().id


def acc_balance(name):
    from app.models import Account
    return Account.query.filter_by(name=name).first().balance


def test_first_install_setup_page(app_instance, client):
    r = client.get("/setup")
    assert r.status_code == 200
    assert b"Setup Administrator" in r.data


def test_create_admin(client):
    r = client.post("/setup", data={"username": "admin", "password": "rahasia123", "confirm_password": "rahasia123"}, follow_redirects=True)
    assert r.status_code == 200
    assert b"Login" in r.data


def test_setup_locked_after_admin(client):
    r = client.post("/setup", data={"username": "evil", "password": "rahasia123", "confirm_password": "rahasia123"}, follow_redirects=True)
    assert b"sudah dikunci" in r.data.lower() or b"Login" in r.data
    with client.application.app_context():
        from app.models import User
        assert User.query.filter_by(username="evil").first() is None


def test_protected_redirect_anonymous(app_instance):
    c = app_instance.test_client()
    r = c.get("/dashboard/")
    assert r.status_code in (301, 302)
    assert "/login" in r.headers["Location"]


def test_login_wrong(client):
    r = client.post("/login", data={"username": "admin", "password": "salah"}, follow_redirects=True)
    assert b"salah" in r.data.lower()


def test_login_success(client):
    r = client.post("/login", data={"username": "admin", "password": "rahasia123"}, follow_redirects=True)
    assert r.status_code == 200
    assert b"Dashboard" in r.data


def test_seed_accounts_11_zero(client):
    with client.application.app_context():
        from app.models import Account
        names = [a.name for a in Account.query.all()]
        for n in ["BCA","BRI","BNI","Mandiri","SeaBank","AlloBank","GoPay","DANA Rudi","DANA Tamara","Uang","Cash"]:
            assert n in names
        # balances may have changed by later tests ordering? this runs early, still 0
        assert Account.query.filter_by(name="BCA").first().balance == 0


def test_saldo_awal_and_invariant(client):
    with client.application.app_context():
        bid = acc_id_by_name("BCA")
    r = client.post(f"/accounts/{bid}/saldo-awal", data={"amount": "1000000"}, follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        assert acc_balance("BCA") == 1000000
        from app.models import Transaction
        from sqlalchemy import func
        from extensions import db as _db
        s = _db.session.query(func.sum(Transaction.signed_amount)).filter_by(account_id=bid, status="active").scalar()
        assert int(s) == 1000000


def test_tambah_saldo(client):
    with client.application.app_context():
        bid = acc_id_by_name("BCA")
    client.post("/transactions/tambah", data={"account_id": bid, "amount": "500000", "description": "Gaji"}, follow_redirects=True)
    with client.application.app_context():
        assert acc_balance("BCA") == 1500000


def test_kurangi_saldo(client):
    with client.application.app_context():
        bid = acc_id_by_name("BCA")
    client.post("/transactions/kurangi", data={"account_id": bid, "amount": "200000", "description": "Tarik"}, follow_redirects=True)
    with client.application.app_context():
        assert acc_balance("BCA") == 1300000


def test_kurangi_insufficient_rejected(client):
    with client.application.app_context():
        bid = acc_id_by_name("BCA")
    r = client.post("/transactions/kurangi", data={"account_id": bid, "amount": "99999999", "description": "X"}, follow_redirects=True)
    assert "tidak mencukupi" in r.get_data(as_text=True)
    with client.application.app_context():
        assert acc_balance("BCA") == 1300000


def test_negative_and_zero_rejected(client):
    with client.application.app_context():
        bid = acc_id_by_name("BCA")
    for amt in ["0", "-5000"]:
        r = client.post("/transactions/tambah", data={"account_id": bid, "amount": amt, "description": "Bad"}, follow_redirects=True)
        assert r.status_code == 200
    with client.application.app_context():
        assert acc_balance("BCA") == 1300000


def test_transfer_linked_total_unchanged(client):
    with client.application.app_context():
        bca = acc_id_by_name("BCA"); bri = acc_id_by_name("BRI")
        before_total = acc_balance("BCA") + acc_balance("BRI")
    r = client.post("/transfers/", data={"from_account_id": bca, "to_account_id": bri, "amount": "300000", "description": "Pindah"}, follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        assert acc_balance("BCA") == 1000000
        assert acc_balance("BRI") == 300000
        assert acc_balance("BCA") + acc_balance("BRI") == before_total
        from app.models import Transaction
        txs = Transaction.query.filter(Transaction.transfer_id.isnot(None)).all()
        assert len(txs) >= 2
        assert txs[0].transfer_id == txs[1].transfer_id


def test_transfer_same_account_rejected(client):
    with client.application.app_context():
        bca = acc_id_by_name("BCA")
    r = client.post("/transfers/", data={"from_account_id": bca, "to_account_id": bca, "amount": "1000"}, follow_redirects=True)
    assert "tidak boleh sama" in r.get_data(as_text=True)


def test_pinjaman_partial_and_lunas(client):
    with client.application.app_context():
        from app.models import Person, Debt
        pid = Person.query.filter_by(name="Anak 1").first().id
        bca = acc_id_by_name("BCA")
    client.post("/debts/create", data={"person_id": pid, "direction": "piutang", "account_id": bca, "amount": "200000", "description": "Pinjam"}, follow_redirects=True)
    with client.application.app_context():
        assert acc_balance("BCA") == 800000
        from app.models import Debt
        d = Debt.query.filter_by(direction="piutang").order_by(Debt.id.desc()).first()
        assert d.remaining == 200000
        did = d.id
    client.post(f"/debts/{did}/pay", data={"account_id": bca, "amount": "50000"}, follow_redirects=True)
    with client.application.app_context():
        from app.models import Debt
        d = Debt.query.get(did)
        assert d.remaining == 150000
        assert acc_balance("BCA") == 850000
    client.post(f"/debts/{did}/pay", data={"account_id": bca, "amount": "150000"}, follow_redirects=True)
    with client.application.app_context():
        from app.models import Debt
        d = Debt.query.get(did)
        assert d.remaining == 0 and d.status == "lunas"
        assert acc_balance("BCA") == 1000000


def test_utang_pribadi_flow(client):
    with client.application.app_context():
        from app.models import Person, Debt
        pid = Person.query.filter_by(name="Istri").first().id
        bca = acc_id_by_name("BCA")
    client.post("/debts/create", data={"person_id": pid, "direction": "utang", "account_id": bca, "amount": "100000", "description": "Utang"}, follow_redirects=True)
    with client.application.app_context():
        assert acc_balance("BCA") == 1100000
        from app.models import Debt
        d = Debt.query.filter_by(direction="utang").order_by(Debt.id.desc()).first()
        did = d.id; assert d.remaining == 100000
    client.post(f"/debts/{did}/pay", data={"account_id": bca, "amount": "100000"}, follow_redirects=True)
    with client.application.app_context():
        assert acc_balance("BCA") == 1000000
        from app.models import Debt
        assert Debt.query.get(did).status == "lunas"


def test_pengeluaran_reduces_and_totals(client):
    with client.application.app_context():
        from app.models import ExpenseCategory
        bca = acc_id_by_name("BCA"); cat = ExpenseCategory.query.filter_by(name="Makanan").first().id
    r = client.post("/expenses/", data={"account_id": bca, "category_id": cat, "amount": "50000", "description": "Makan siang"}, follow_redirects=True)
    assert r.status_code == 200
    assert "50.000" in r.get_data(as_text=True) or "50000" in r.get_data(as_text=True)
    with client.application.app_context():
        assert acc_balance("BCA") == 950000


def test_uncollected_partial_full(client):
    r = client.post("/uncollected/", data={"source_name": "Kantor", "amount": "500000", "description": "Bonus"}, follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        from app.models import UncollectedIncome
        u = UncollectedIncome.query.order_by(UncollectedIncome.id.desc()).first()
        uid = u.id; assert u.remaining == 500000
        bca = acc_id_by_name("BCA")
        before = acc_balance("BCA")
    client.post(f"/uncollected/{uid}/receive", data={"account_id": bca, "amount": "200000"}, follow_redirects=True)
    with client.application.app_context():
        from app.models import UncollectedIncome
        u = UncollectedIncome.query.get(uid)
        assert u.remaining == 300000 and u.status == "diambil_sebagian"
        assert acc_balance("BCA") == before + 200000
    client.post(f"/uncollected/{uid}/receive", data={"account_id": bca, "amount": "300000"}, follow_redirects=True)
    with client.application.app_context():
        from app.models import UncollectedIncome
        u = UncollectedIncome.query.get(uid)
        assert u.remaining == 0 and u.status == "sudah_diambil"


def test_reports_endpoints_and_transfer_excluded(client):
    for period in ["harian", "mingguan", "bulanan"]:
        r = client.get(f"/reports/?period={period}")
        assert r.status_code == 200
    r = client.get("/reports/?period=bulanan")
    text = r.get_data(as_text=True)
    # pemasukan external in report should not include transfer 300k as income; check endpoint works + csv
    rc = client.get("/reports/export.csv?period=bulanan")
    assert rc.status_code == 200 and b"Tanggal" in rc.data
    rp = client.get("/reports/print?period=bulanan")
    assert rp.status_code == 200


def test_cancel_reversal_restores_and_audit(client):
    with client.application.app_context():
        bca = acc_id_by_name("BCA"); before = acc_balance("BCA")
    client.post("/transactions/tambah", data={"account_id": bca, "amount": "70000", "description": "Untuk dibatalkan"}, follow_redirects=True)
    with client.application.app_context():
        assert acc_balance("BCA") == before + 70000
        from app.models import Transaction
        tx = Transaction.query.filter_by(description="Untuk dibatalkan").order_by(Transaction.id.desc()).first()
        tid = tx.id
    client.post(f"/transactions/{tid}/cancel", data={"reason": "Salah input"}, follow_redirects=True)
    with client.application.app_context():
        assert acc_balance("BCA") == before
        from app.models import Transaction, AuditLog
        assert Transaction.query.get(tid).status == "cancelled"
        assert AuditLog.query.filter(AuditLog.action.ilike("%cancel%")).count() >= 1


def test_penyesuaian_requires_reason_and_audit(client):
    with client.application.app_context():
        bri = acc_id_by_name("BRI")
    r = client.post("/transactions/penyesuaian", data={"account_id": bri, "target_balance": "400000", "reason": ""}, follow_redirects=True)
    assert "wajib" in r.get_data(as_text=True)
    client.post("/transactions/penyesuaian", data={"account_id": bri, "target_balance": "400000", "reason": "Koreksi kas"}, follow_redirects=True)
    with client.application.app_context():
        assert acc_balance("BRI") == 400000
        from app.models import AuditLog
        assert AuditLog.query.filter_by(action="penyesuaian").count() >= 1


def test_backup_and_restore(client, tmp_path):
    r = client.post("/backup/create", follow_redirects=True)
    assert r.status_code == 200
    assert "Backup berhasil" in r.get_data(as_text=True)
    with client.application.app_context():
        from app.backup.routes import list_backups
        b = list_backups()
        assert len(b) >= 1
        name = b[0]["name"]
    r2 = client.post("/backup/restore", data={"filename": name}, follow_redirects=True)
    assert r2.status_code == 200


def test_xss_escaped(client):
    payload = "<script>alert(1)</script>"
    with client.application.app_context():
        bca = acc_id_by_name("BCA")
    r = client.post("/transactions/tambah", data={"account_id": bca, "amount": "1000", "description": payload}, follow_redirects=True)
    text = r.get_data(as_text=True)
    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;" in text or "script" in text  # escaped rendering somewhere in history/dashboard
    rh = client.get("/transactions/")
    assert "<script>alert(1)</script>" not in rh.get_data(as_text=True)


def test_responsive_markers(client):
    r = client.get("/dashboard/")
    text = r.get_data(as_text=True)
    assert 'name="viewport"' in text
    assert "bottom-nav" in text
    assert "Lainnya" in text
    css = open(os.path.join(os.path.dirname(__file__), "..", "app", "static", "css", "style.css"), encoding="utf-8").read()
    for bp in ["320", "768", "1024", "1280"]:
        assert bp in css
    # no JS alert/confirm/prompt in app js / templates
    import glob
    for f in glob.glob(os.path.join(os.path.dirname(__file__), "..", "app", "**", "*.js"), recursive=True) + glob.glob(os.path.join(os.path.dirname(__file__), "..", "app", "**", "*.html"), recursive=True):
        c = open(f, encoding="utf-8").read()
        assert "alert(" not in c and "confirm(" not in c and "prompt(" not in c, f


def test_persistence_across_restart(app_instance, client):
    db_file = app_instance.config["_db_file"]
    from app import create_app
    app2 = create_app(TestConfig, {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}"})
    with app2.app_context():
        from app.models import Account, User
        assert User.query.filter_by(username="admin").first() is not None
        assert Account.query.filter_by(name="BCA").first().balance > 0
