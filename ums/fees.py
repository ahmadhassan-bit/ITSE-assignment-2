"""Fee Management service -- Saad's implementation responsibility."""
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .validation import required_text


def _amount_to_paisa(value):
    if isinstance(value, bool):
        raise ValueError("amount must be a positive monetary value")
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValueError("amount must be a valid monetary value") from None
    if amount <= 0 or Decimal(str(value)) != amount:
        raise ValueError("amount must be positive and have at most two decimal places")
    return int(amount * 100)


def _valid_due_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except (ValueError, TypeError):
        raise ValueError("due date must be a valid date") from None


def create_invoice(db, student_id, amount, due_date):
    student = db.execute("SELECT id FROM students WHERE id=?", (student_id,)).fetchone()
    if student is None:
        raise ValueError("student not found")
    paisa = _amount_to_paisa(amount)
    due = _valid_due_date(due_date)
    with db:
        cursor = db.execute(
            "INSERT INTO invoices(student_id,amount_paisa,due_date) VALUES (?,?,?)",
            (student_id, paisa, due),
        )
    return get_invoice(db, cursor.lastrowid)


def get_invoice(db, invoice_id):
    row = db.execute(
        """SELECT i.id, i.student_id, s.roll_number, s.name, i.amount_paisa,
                  i.due_date
           FROM invoices i JOIN students s ON s.id=i.student_id
           WHERE i.id=?""", (invoice_id,)
    ).fetchone()
    if row is None:
        raise ValueError("invoice not found")
    return dict(row)


def record_payment(db, invoice_id, amount):
    paisa = _amount_to_paisa(amount)
    with db:
        invoice = db.execute(
            "SELECT amount_paisa FROM invoices WHERE id=?", (invoice_id,)
        ).fetchone()
        if invoice is None:
            raise ValueError("invoice not found")
        paid = db.execute(
            "SELECT COALESCE(SUM(amount_paisa),0) AS paid FROM payments WHERE invoice_id=?",
            (invoice_id,),
        ).fetchone()["paid"]
        if paisa > invoice["amount_paisa"] - paid:
            raise ValueError("payment exceeds outstanding balance")
        cursor = db.execute(
            "INSERT INTO payments(invoice_id,amount_paisa) VALUES (?,?)",
            (invoice_id, paisa),
        )
    return get_payment(db, cursor.lastrowid)


def get_payment(db, payment_id):
    row = db.execute(
        """SELECT p.id AS payment_id, p.invoice_id, i.student_id,
                  s.roll_number, s.name, p.amount_paisa, p.recorded_at
           FROM payments p
           JOIN invoices i ON i.id=p.invoice_id
           JOIN students s ON s.id=i.student_id
           WHERE p.id=?""", (payment_id,)
    ).fetchone()
    if row is None:
        raise ValueError("payment not found")
    return dict(row)


def view_balances(db, student_id):
    if db.execute("SELECT id FROM students WHERE id=?", (student_id,)).fetchone() is None:
        raise ValueError("student not found")
    rows = db.execute(
        """SELECT i.id AS invoice_id, i.amount_paisa,
                  COALESCE(SUM(p.amount_paisa),0) AS paid_paisa, i.due_date
           FROM invoices i LEFT JOIN payments p ON p.invoice_id=i.id
           WHERE i.student_id=? GROUP BY i.id ORDER BY i.due_date,i.id""",
        (student_id,),
    ).fetchall()
    result = []
    for row in rows:
        outstanding = row["amount_paisa"] - row["paid_paisa"]
        status = "Paid" if outstanding == 0 else ("Partial" if row["paid_paisa"] else "Unpaid")
        result.append({
            "invoice_id": row["invoice_id"], "amount_paisa": row["amount_paisa"],
            "paid_paisa": row["paid_paisa"], "outstanding_paisa": outstanding,
            "due_date": row["due_date"], "status": status,
        })
    return result


def receipt(db, payment_id):
    return get_payment(db, payment_id)


def init_app(app):
    from flask import render_template, request
    @app.get("/fees")
    def index():
        from .students import list_students
        students = list_students(get_db_for_app())
        return render_template("fees.html", students=students)

    @app.post("/fees/invoices")
    def invoice_create():
        create_invoice(get_db_for_app(), int(request.form["student_id"]),
                       request.form.get("amount", ""), request.form.get("due_date", ""))
        from flask import redirect, url_for, flash
        flash("Invoice created.")
        return redirect(url_for("fees.index"))

    @app.post("/fees/payments")
    def payment_create():
        record_payment(get_db_for_app(), int(request.form["invoice_id"]),
                       request.form.get("amount", ""))
        from flask import redirect, url_for, flash
        flash("Payment recorded.")
        return redirect(url_for("fees.index"))

    @app.get("/fees/balances/<int:student_id>")
    def balances(student_id):
        return render_template("balances.html", balances=view_balances(get_db_for_app(), student_id))

    @app.get("/fees/receipts/<int:payment_id>")
    def receipt_view(payment_id):
        return render_template("receipt.html", receipt=receipt(get_db_for_app(), payment_id))


def get_db_for_app():
    from .web import get_db
    return get_db()
