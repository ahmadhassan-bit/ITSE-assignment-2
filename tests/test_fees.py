import unittest

from ums.db import connect
from ums.fees import create_invoice, record_payment, view_balances, receipt
from ums.students import create_student


class FeeTests(unittest.TestCase):
    def setUp(self):
        self.db = connect()
        self.addCleanup(self.db.close)
        self.student = create_student(self.db, "F26-FEE1", "Fee Student", "fee@example.test", "BSE")

    def test_generate_invoice_stores_paisa_and_rejects_bad_amounts(self):
        invoice = create_invoice(self.db, self.student["id"], "1250.50", "2026-10-31")
        self.assertEqual(invoice["amount_paisa"], 125050)
        before = self.db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        for amount in ("0", "-1", "1.999", "abc"):
            with self.assertRaises(ValueError):
                create_invoice(self.db, self.student["id"], amount, "2026-10-31")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0], before)

    def test_invoice_rejects_missing_student_and_invalid_date(self):
        for student_id, date in ((999, "2026-10-31"), (self.student["id"], "bad")):
            with self.assertRaises(ValueError):
                create_invoice(self.db, student_id, "100.00", date)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0], 0)

    def test_record_payment_reduces_balance_and_rejects_overpayment(self):
        invoice = create_invoice(self.db, self.student["id"], "1000.00", "2026-10-31")
        payment = record_payment(self.db, invoice["id"], "250.00")
        self.assertEqual(payment["amount_paisa"], 25000)
        self.assertEqual(view_balances(self.db, self.student["id"])[0]["outstanding_paisa"], 75000)
        with self.assertRaises(ValueError):
            record_payment(self.db, invoice["id"], "800.01")
        self.assertEqual(len(self.db.execute("SELECT * FROM payments").fetchall()), 1)

    def test_payment_rejects_zero_negative_and_missing_invoice(self):
        invoice = create_invoice(self.db, self.student["id"], "100.00", "2026-10-31")
        for amount in ("0", "-1"):
            with self.assertRaises(ValueError):
                record_payment(self.db, invoice["id"], amount)
        with self.assertRaises(ValueError):
            record_payment(self.db, 999, "10.00")

    def test_balances_show_unpaid_partial_paid_and_empty_state(self):
        self.assertEqual(view_balances(self.db, self.student["id"]), [])
        a = create_invoice(self.db, self.student["id"], "100.00", "2026-10-01")
        b = create_invoice(self.db, self.student["id"], "200.00", "2026-10-02")
        record_payment(self.db, b["id"], "200.00")
        record_payment(self.db, a["id"], "25.00")
        states = {x["invoice_id"]: x for x in view_balances(self.db, self.student["id"])}
        self.assertEqual(states[a["id"]]["status"], "Partial")
        self.assertEqual(states[a["id"]]["outstanding_paisa"], 7500)
        self.assertEqual(states[b["id"]]["status"], "Paid")

    def test_receipt_is_read_only_and_exact(self):
        invoice = create_invoice(self.db, self.student["id"], "50.00", "2026-10-31")
        payment = record_payment(self.db, invoice["id"], "50.00")
        before = self.db.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
        result = receipt(self.db, payment["payment_id"])
        self.assertEqual(result["amount_paisa"], 5000)
        self.assertEqual(result["roll_number"], "F26-FEE1")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM payments").fetchone()[0], before)
