import os
import tempfile
import unittest

from app import create_app


class UMSTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.app = create_app(self.tmp.name)
        self.client = self.app.test_client()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_register_student_and_retrieve_by_roll(self):
        response = self.client.post("/students", json={
            "roll_number": "BSE123",
            "name": "Ali Khan",
            "email": "ali@example.com",
            "programme": "BS Software Engineering"
        })
        self.assertEqual(response.status_code, 201)
        student = response.get_json()
        self.assertEqual(student["status"], "active")

        response = self.client.get("/students?roll_number=bse123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()), 1)
        self.assertEqual(response.get_json()[0]["roll_number"], "BSE123")

    def test_duplicate_roll_number_is_rejected_case_insensitively(self):
        payload = {
            "roll_number": "BSE124",
            "name": "Sara",
            "email": "sara@example.com",
            "programme": "BSSE"
        }
        self.assertEqual(self.client.post("/students", json=payload).status_code, 201)
        duplicate = dict(payload, roll_number=" bse124 ")
        response = self.client.post("/students", json=duplicate)
        self.assertEqual(response.status_code, 409)

    def test_invalid_registration_is_rejected(self):
        response = self.client.post("/students", json={
            "roll_number": "",
            "name": "",
            "email": "not-an-email",
            "programme": ""
        })
        self.assertEqual(response.status_code, 400)

    def test_update_student_preserves_id_and_roll_number(self):
        created = self.client.post("/students", json={
            "roll_number": "BSE125",
            "name": "Old Name",
            "email": "old@example.com",
            "programme": "BSSE"
        }).get_json()

        response = self.client.put(f"/students/{created['id']}", json={
            "name": "New Name",
            "email": "new@example.com",
            "programme": "BSCS"
        })
        self.assertEqual(response.status_code, 200)
        updated = response.get_json()
        self.assertEqual(updated["id"], created["id"])
        self.assertEqual(updated["roll_number"], "BSE125")
        self.assertEqual(updated["name"], "New Name")

    def test_invalid_update_does_not_change_existing_data(self):
        created = self.client.post("/students", json={
            "roll_number": "BSE126",
            "name": "Stable Name",
            "email": "stable@example.com",
            "programme": "BSSE"
        }).get_json()

        response = self.client.put(f"/students/{created['id']}", json={
            "name": "",
            "email": "bad",
            "programme": ""
        })
        self.assertEqual(response.status_code, 400)

        current = self.client.get(f"/students/{created['id']}").get_json()
        self.assertEqual(current["name"], "Stable Name")
        self.assertEqual(current["email"], "stable@example.com")

    def test_student_status_can_be_deactivated_and_restored(self):
        created = self.client.post("/students", json={
            "roll_number": "BSE127",
            "name": "Status User",
            "email": "status@example.com",
            "programme": "BSSE"
        }).get_json()

        response = self.client.patch(f"/students/{created['id']}/status", json={"status": "inactive"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "inactive")

        response = self.client.patch(f"/students/{created['id']}/status", json={"status": "active"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "active")

    def test_invalid_status_is_rejected(self):
        created = self.client.post("/students", json={
            "roll_number": "BSE128",
            "name": "Status User",
            "email": "status2@example.com",
            "programme": "BSSE"
        }).get_json()

        response = self.client.patch(f"/students/{created['id']}/status", json={"status": "graduated"})
        self.assertEqual(response.status_code, 400)

    def test_exam_session_rejects_invalid_interval(self):
        response = self.client.post("/exams", json={
            "course": "SE1001",
            "title": "Software Engineering",
            "start": "2026-10-01T09:00",
            "end": "2026-10-01T09:00",
            "room": "A-101"
        })
        self.assertEqual(response.status_code, 400)

    def test_exam_session_rejects_room_overlap_but_allows_adjacent(self):
        first = {
            "course": "SE1001",
            "title": "Software Engineering",
            "start": "2026-10-01T09:00",
            "end": "2026-10-01T10:00",
            "room": "A-101"
        }
        self.assertEqual(self.client.post("/exams", json=first).status_code, 201)

        overlap = dict(first, course="CS2001", start="2026-10-01T09:30", end="2026-10-01T10:30")
        self.assertEqual(self.client.post("/exams", json=overlap).status_code, 409)

        adjacent = dict(first, course="CS2002", start="2026-10-01T10:00", end="2026-10-01T11:00")
        self.assertEqual(self.client.post("/exams", json=adjacent).status_code, 201)

    def test_exam_schedule_is_chronological_and_date_filter_works(self):
        self.client.post("/exams", json={
            "course": "CS2", "title": "Later",
            "start": "2026-10-02T11:00", "end": "2026-10-02T12:00", "room": "B-2"
        })
        self.client.post("/exams", json={
            "course": "CS1", "title": "Earlier",
            "start": "2026-10-02T09:00", "end": "2026-10-02T10:00", "room": "B-1"
        })
        response = self.client.get("/exams?date=2026-10-02")
        self.assertEqual(response.status_code, 200)
        exams = response.get_json()
        self.assertEqual([e["title"] for e in exams], ["Earlier", "Later"])

    def test_invalid_exam_date_filter_is_rejected(self):
        response = self.client.get("/exams?date=not-a-date")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
