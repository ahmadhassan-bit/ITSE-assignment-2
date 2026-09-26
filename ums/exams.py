"""Exam sessions and schedule -- Ahmad. Candidate registration is partner-owned."""
from datetime import datetime

from .validation import required_text


def local_datetime(value, field):
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M").isoformat(timespec="minutes")
    except (ValueError, TypeError):
        raise ValueError(f"{field} must be a valid local date and time") from None


def create_exam(db, course_code, title, starts_at, ends_at, room):
    values = required_text(dict(course_code=course_code, title=title, room=room))
    start = local_datetime(starts_at, "start time")
    end = local_datetime(ends_at, "end time")
    if end <= start:
        raise ValueError("end time must be after start time")
    # Serialize the check and insert so a concurrent room booking cannot race it.
    with db:
        db.execute("BEGIN IMMEDIATE")
        overlap = db.execute(
            "SELECT id FROM exams WHERE room = ? AND starts_at < ? AND ends_at > ?",
            (values["room"], end, start),
        ).fetchone()
        if overlap:
            raise ValueError("room already has an overlapping examination")
        cursor = db.execute(
            "INSERT INTO exams(course_code,title,starts_at,ends_at,room) VALUES (?,?,?,?,?)",
            (values["course_code"].upper(), values["title"], start, end, values["room"].upper()),
        )
    return get_exam(db, cursor.lastrowid)


def get_exam(db, exam_id):
    row = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
    if row is None:
        raise ValueError("examination not found")
    return dict(row)


def list_exams(db, date=None):
    parameters = ()
    where = ""
    if date:
        try:
            date = datetime.strptime(date, "%Y-%m-%d").date().isoformat()
        except (ValueError, TypeError):
            raise ValueError("date filter must be a valid date") from None
        where = " WHERE substr(starts_at,1,10)=?"
        parameters = (date,)
    return [dict(row) for row in db.execute(
        "SELECT * FROM exams" + where + " ORDER BY starts_at,id", parameters
    ).fetchall()]

