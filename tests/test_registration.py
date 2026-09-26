import os
import tempfile
import unittest

from ums.db import connect
from ums.students import create_student


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.db = connect()
        self.addCleanup(self.db.close)

    def register(self, **overrides):
        values = dict(roll_number="F26-0001", name="Sample Student",
                      email="student@example.test", programme="BSE")
        values.update(overrides)
        return create_student(self.db, **values)

    def test_valid_student_has_stable_id_and_active_status(self):
        student = self.register()
        self.assertIsInstance(student["id"], int)
        self.assertEqual(student["status"], "active")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM students").fetchone()[0], 1)

    def test_duplicate_roll_number_is_rejected_case_insensitively(self):
        self.register()
        with self.assertRaisesRegex(ValueError, "roll number"):
            self.register(roll_number=" f26-0001 ")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM students").fetchone()[0], 1)

    def test_required_fields_are_rejected_without_saving(self):
        for field in ("roll_number", "name", "email", "programme"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field.replace("_", " ")):
                    self.register(**{field: " "})
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM students").fetchone()[0], 0)

    def test_invalid_email_is_rejected_without_saving(self):
        with self.assertRaisesRegex(ValueError, "email"):
            self.register(email="not-an-email")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM students").fetchone()[0], 0)

    def test_saved_student_survives_reopening_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "test.sqlite")
            db = connect(path)
            try:
                student = create_student(db, "F26-0002", "Second Student", "second@example.test", "BSE")
            finally:
                db.close()
            reopened = connect(path)
            try:
                row = reopened.execute("SELECT * FROM students WHERE id = ?", (student["id"],)).fetchone()
                self.assertEqual(row["roll_number"], "F26-0002")
            finally:
                reopened.close()

