"""Student Management service -- Ahmad's implementation responsibility."""
import re
import sqlite3


def create_student(db, roll_number, name, email, programme):
    values = dict(roll_number=roll_number, name=name, email=email, programme=programme)
    for field, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field.replace('_', ' ')} is required")
        values[field] = value.strip()
        if len(values[field]) > 200:
            raise ValueError(f"{field.replace('_', ' ')} must be 200 characters or fewer")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"]):
        raise ValueError("email must have a valid address format")
    try:
        with db:
            cursor = db.execute(
                "INSERT INTO students (roll_number,name,email,programme) VALUES (?,?,?,?)",
                (values["roll_number"].upper(), values["name"], values["email"], values["programme"]),
            )
    except sqlite3.IntegrityError as error:
        raise ValueError("roll number already exists") from error
    return get_student(db, cursor.lastrowid)


def get_student(db, student_id):
    row = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if row is None:
        raise ValueError("student not found")
    return dict(row)


def list_students(db, query=""):
    if not isinstance(query, str):
        raise ValueError("search must be text")
    query = query.strip()
    if len(query) > 200:
        raise ValueError("search must be 200 characters or fewer")
    rows = db.execute(
        "SELECT * FROM students WHERE instr(lower(roll_number),lower(?)) > 0 "
        "OR instr(lower(name),lower(?)) > 0 ORDER BY roll_number,id", (query, query)
    ).fetchall()
    return [dict(row) for row in rows]


def update_student(db, student_id, name, email, programme):
    get_student(db, student_id)
    values = dict(name=name, email=email, programme=programme)
    for field, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field.replace('_', ' ')} is required")
        values[field] = value.strip()
        if len(values[field]) > 200:
            raise ValueError(f"{field.replace('_', ' ')} must be 200 characters or fewer")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"]):
        raise ValueError("email must have a valid address format")
    with db:
        db.execute("UPDATE students SET name=?,email=?,programme=? WHERE id=?",
                   (values["name"], values["email"], values["programme"], student_id))
    return get_student(db, student_id)


def set_student_status(db, student_id, status):
    get_student(db, student_id)
    if status not in ("active", "inactive"):
        raise ValueError("status must be active or inactive")
    with db:
        db.execute("UPDATE students SET status=? WHERE id=?", (status, student_id))
    return get_student(db, student_id)

