import unittest

from ums.db import connect
from ums.exams import create_exam
from ums.registrations import register_student_for_exam, admit_card
from ums.students import create_student


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.db = connect()
        self.addCleanup(self.db.close)
        self.student = create_student(self.db, "F26-EX01", "Exam Student", "exam@example.test", "BSE")
        self.exam = create_exam(self.db, "SE1001", "ITSE", "2026-11-01T09:00", "2026-11-01T11:00", "A1")

    def test_register_active_student_and_duplicate_is_rejected(self):
        reg = register_student_for_exam(self.db, self.student["id"], self.exam["id"])
        self.assertEqual(reg["roll_number"], "F26-EX01")
        with self.assertRaisesRegex(ValueError, "already registered"):
            register_student_for_exam(self.db, self.student["id"], self.exam["id"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM registrations").fetchone()[0], 1)

    def test_inactive_and_missing_student_or_exam_are_rejected(self):
        self.db.execute("UPDATE students SET status='inactive' WHERE id=?", (self.student["id"],))
        with self.assertRaisesRegex(ValueError, "inactive"):
            register_student_for_exam(self.db, self.student["id"], self.exam["id"])
        with self.assertRaises(ValueError):
            register_student_for_exam(self.db, 999, self.exam["id"])
        self.db.execute("UPDATE students SET status='active' WHERE id=?", (self.student["id"],))
        with self.assertRaises(ValueError):
            register_student_for_exam(self.db, self.student["id"], 999)

    def test_student_time_clash_is_rejected(self):
        first = register_student_for_exam(self.db, self.student["id"], self.exam["id"])
        clash = create_exam(self.db, "CS1004", "DS", "2026-11-01T10:00", "2026-11-01T12:00", "B1")
        with self.assertRaisesRegex(ValueError, "overlapping"):
            register_student_for_exam(self.db, self.student["id"], clash["id"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM registrations").fetchone()[0], 1)

    def test_admit_card_contains_required_fields_and_is_read_only(self):
        reg = register_student_for_exam(self.db, self.student["id"], self.exam["id"])
        before = self.db.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
        card = admit_card(self.db, reg["registration_id"])
        for field in ("name", "roll_number", "registration_id", "course_code", "starts_at", "ends_at", "room"):
            self.assertIn(field, card)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM registrations").fetchone()[0], before)

    def test_admit_card_rejects_inactive_student(self):
        reg = register_student_for_exam(self.db, self.student["id"], self.exam["id"])
        self.db.execute("UPDATE students SET status='inactive' WHERE id=?", (self.student["id"],))
        with self.assertRaisesRegex(ValueError, "active"):
            admit_card(self.db, reg["registration_id"])
