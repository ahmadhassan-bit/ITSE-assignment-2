import unittest

from ums.db import connect
from ums.students import create_student, get_student, list_students, set_student_status, update_student


class StudentTests(unittest.TestCase):
    def setUp(self):
        self.db = connect()
        self.addCleanup(self.db.close)
        self.student = create_student(self.db, "F26-0001", "Sample Student", "s@example.test", "BSE")

    def test_search_matches_roll_and_partial_name_case_insensitively(self):
        for query in ("f26-0001", "sAmPle"):
            self.assertEqual(list_students(self.db, query)[0]["id"], self.student["id"])

    def test_empty_and_special_character_searches_do_not_change_data(self):
        for query in ("Nobody", "' OR 1=1 --", "%", "_"):
            self.assertEqual(list_students(self.db, query), [])
        self.assertEqual(len(list_students(self.db)), 1)

    def test_update_preserves_identity(self):
        updated = update_student(self.db, self.student["id"], "New Name", "new@example.test", "BSCS")
        self.assertEqual(updated["name"], "New Name")
        self.assertEqual(updated["programme"], "BSCS")
        for field in ("id", "roll_number"):
            self.assertEqual(updated[field], self.student[field])

    def test_invalid_update_is_atomic(self):
        with self.assertRaises(ValueError):
            update_student(self.db, self.student["id"], "Changed", "bad", "BSCS")
        self.assertEqual(get_student(self.db, self.student["id"]), self.student)

    def test_missing_student_cannot_be_updated_or_activated(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            update_student(self.db, 999, "Missing", "m@example.test", "BSE")
        with self.assertRaisesRegex(ValueError, "not found"):
            set_student_status(self.db, 999, "active")

    def test_status_change_preserves_linked_invoice(self):
        with self.db:
            self.db.execute("INSERT INTO invoices(student_id,amount_paisa,due_date) VALUES (?,?,?)",
                            (self.student["id"], 50000, "2026-10-01"))
        for status in ("inactive", "active"):
            changed = set_student_status(self.db, self.student["id"], status)
            self.assertEqual(changed["status"], status)
            self.assertEqual(changed["name"], self.student["name"])
            self.assertEqual(self.db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0], 1)

    def test_invalid_status_does_not_change_student(self):
        with self.assertRaises(ValueError):
            set_student_status(self.db, self.student["id"], "deleted")
        self.assertEqual(get_student(self.db, self.student["id"]), self.student)

    def test_required_and_overlong_values_are_rejected_on_update(self):
        for field, value in (("name", ""), ("programme", ""), ("name", "x" * 201)):
            data = {"name": "Valid", "email": "valid@example.test", "programme": "BSE"}
            data[field] = value
            with self.assertRaises(ValueError):
                update_student(self.db, self.student["id"], **data)
        self.assertEqual(get_student(self.db, self.student["id"]), self.student)
