import os
import re
import tempfile
import unittest

from ums.db import connect
from ums.students import create_student, get_student
from ums.web import create_app


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "test.sqlite")
        self.app = create_app({"TESTING": True, "DATABASE": self.path, "SECRET_KEY": "test-only-key"})
        self.client = self.app.test_client()

    def token(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))[1]

    def test_dashboard_and_empty_pages_render(self):
        for path, marker in (("/", "university records"), ("/students", "No students found"),
                             ("/exams", "No examinations found")):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(marker, response.get_data(as_text=True))

    def test_registration_and_search_through_forms(self):
        data = dict(roll_number="F26-0090", name="Web Student", email="web@example.test", programme="BSE",
                    csrf_token=self.token("/students/new"))
        response = self.client.post("/students/new", data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Student registered", response.get_data(as_text=True))
        self.assertIn("Web Student", self.client.get("/students?q=F26-0090").get_data(as_text=True))

    def test_post_without_csrf_is_rejected(self):
        response = self.client.post("/students/new", data={"name": "Untrusted"})
        self.assertEqual(response.status_code, 400)
        db = connect(self.path)
        self.addCleanup(db.close)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM students").fetchone()[0], 0)

    def test_invalid_email_returns_validation_message(self):
        token = self.token("/students/new")
        response = self.client.post("/students/new", data=dict(roll_number="F26-0090", name="Student",
                                    email="bad", programme="BSE", csrf_token=token))
        self.assertEqual(response.status_code, 400)
        self.assertIn("email must", response.get_data(as_text=True))

    def test_non_ascii_csrf_token_is_rejected_cleanly(self):
        self.token("/students/new")
        response = self.client.post("/students/new", data={"csrf_token": "invalid-\u00e9"})
        self.assertEqual(response.status_code, 400)

    def test_user_content_is_escaped_in_student_list(self):
        db = connect(self.path)
        try:
            create_student(db, "F26-0090", "<script>alert(1)</script>", "s@example.test", "BSE")
        finally:
            db.close()
        page = self.client.get("/students").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_student_update_and_status_forms(self):
        db = connect(self.path)
        try:
            student = create_student(db, "F26-0090", "Student", "s@example.test", "BSE")
        finally:
            db.close()
        token = self.token(f"/students/{student['id']}/edit")
        response = self.client.post(f"/students/{student['id']}/edit", data=dict(name="Updated",
                                    email="u@example.test", programme="BSE", csrf_token=token))
        self.assertEqual(response.status_code, 302)
        response = self.client.post(f"/students/{student['id']}/status", data=dict(status="inactive", csrf_token=token))
        self.assertEqual(response.status_code, 302)
        db = connect(self.path)
        try:
            updated = get_student(db, student["id"])
            self.assertEqual(updated["name"], "Updated")
            self.assertEqual(updated["status"], "inactive")
        finally:
            db.close()

    def test_exam_form_schedule_and_conflict(self):
        data = dict(course_code="SE1001", title="ITSE", starts_at="2026-10-10T09:00",
                    ends_at="2026-10-10T11:00", room="A1", csrf_token=self.token("/exams/new"))
        response = self.client.post("/exams/new", data=data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("SE1001", response.get_data(as_text=True))
        response = self.client.post("/exams/new", data=data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("overlapping", response.get_data(as_text=True))
