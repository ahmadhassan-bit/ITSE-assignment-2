import unittest

from ums.db import connect
from ums.exams import create_exam, list_exams


class ExamTests(unittest.TestCase):
    def setUp(self):
        self.db = connect()
        self.addCleanup(self.db.close)

    def add_exam(self, **overrides):
        fields = dict(course_code="SE1001", title="Introduction to Software Engineering",
                      starts_at="2026-10-10T09:00", ends_at="2026-10-10T11:00", room="A1")
        fields.update(overrides)
        return create_exam(self.db, **fields)

    def test_valid_session_is_saved(self):
        exam = self.add_exam()
        self.assertEqual(exam["course_code"], "SE1001")
        self.assertEqual(list_exams(self.db)[0]["id"], exam["id"])

    def test_invalid_interval_and_invalid_dates_are_rejected(self):
        for fields in ({"ends_at": "2026-10-10T09:00"}, {"ends_at": "2026-10-10T08:00"},
                       {"starts_at": "2026-02-30T09:00"}, {"ends_at": "bad"}):
            with self.assertRaises(ValueError):
                self.add_exam(**fields)
        self.assertEqual(list_exams(self.db), [])

    def test_required_fields_are_rejected(self):
        for field in ("course_code", "title", "room"):
            with self.assertRaises(ValueError):
                self.add_exam(**{field: " "})

    def test_room_overlap_is_case_insensitive_and_atomic(self):
        self.add_exam()
        with self.assertRaisesRegex(ValueError, "overlapping"):
            self.add_exam(starts_at="2026-10-10T10:00", ends_at="2026-10-10T12:00", room="a1")
        self.assertEqual(len(list_exams(self.db)), 1)

    def test_enclosing_interval_is_a_conflict(self):
        self.add_exam()
        with self.assertRaises(ValueError):
            self.add_exam(starts_at="2026-10-10T08:00", ends_at="2026-10-10T12:00")

    def test_adjacent_sessions_and_different_rooms_are_allowed(self):
        self.add_exam()
        self.add_exam(starts_at="2026-10-10T11:00", ends_at="2026-10-10T12:00")
        self.add_exam(room="B1")
        self.assertEqual(len(list_exams(self.db)), 3)

    def test_schedule_is_sorted_and_filtered_by_date(self):
        late = self.add_exam(starts_at="2026-10-11T09:00", ends_at="2026-10-11T11:00")
        early = self.add_exam()
        self.assertEqual([x["id"] for x in list_exams(self.db)], [early["id"], late["id"]])
        self.assertEqual(list_exams(self.db, "2026-10-10"), [early])
        self.assertEqual(list_exams(self.db, "2026-12-01"), [])
        with self.assertRaisesRegex(ValueError, "date filter"):
            list_exams(self.db, "2026-02-30")

