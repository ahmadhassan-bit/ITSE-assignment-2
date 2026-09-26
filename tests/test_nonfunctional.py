import os
import tempfile
import time
import unittest

from ums.db import connect
from ums.students import list_students


class NonfunctionalTests(unittest.TestCase):
    def test_search_1000_records_completes_within_two_seconds(self):
        db = connect()
        self.addCleanup(db.close)
        with db:
            db.executemany("INSERT INTO students(roll_number,name,email,programme) VALUES (?,?,?,?)",
                [(f"F26-{i:04}", f"Sample Student {i}", f"s{i}@example.test", "BSE") for i in range(1000)])
        started = time.perf_counter()
        rows = list_students(db, "Student")
        elapsed = time.perf_counter() - started
        self.assertEqual(len(rows), 1000)
        self.assertLess(elapsed, 2.0)

    def test_sqlite_backup_restores_student_records(self):
        with tempfile.TemporaryDirectory() as directory:
            source = connect(os.path.join(directory, "source.sqlite"))
            backup = connect(os.path.join(directory, "backup.sqlite"))
            try:
                with source:
                    source.execute("INSERT INTO students(roll_number,name,email,programme) VALUES (?,?,?,?)",
                                   ("F26-0001", "Backup Student", "b@example.test", "BSE"))
                source.backup(backup)
                self.assertEqual(backup.execute("SELECT name FROM students").fetchone()[0], "Backup Student")
            finally:
                backup.close()
                source.close()
