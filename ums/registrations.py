"""Examination candidate registration and admit cards -- Saad's implementation."""
from datetime import datetime


def register_student_for_exam(db, student_id, exam_id):
    student = db.execute("SELECT id,status FROM students WHERE id=?", (student_id,)).fetchone()
    if student is None:
        raise ValueError("student not found")
    if student["status"] != "active":
        raise ValueError("student is inactive")
    exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
    if exam is None:
        raise ValueError("examination not found")
    duplicate = db.execute(
        "SELECT id FROM registrations WHERE student_id=? AND exam_id=?",
        (student_id, exam_id),
    ).fetchone()
    if duplicate:
        raise ValueError("student is already registered for this examination")
    clash = db.execute(
        """SELECT e.id FROM registrations r JOIN exams e ON e.id=r.exam_id
           WHERE r.student_id=? AND e.starts_at < ? AND e.ends_at > ?""",
        (student_id, exam["ends_at"], exam["starts_at"]),
    ).fetchone()
    if clash:
        raise ValueError("student has an overlapping examination")
    with db:
        cursor = db.execute(
            "INSERT INTO registrations(student_id,exam_id) VALUES (?,?)",
            (student_id, exam_id),
        )
    return get_registration(db, cursor.lastrowid)


def get_registration(db, registration_id):
    row = db.execute(
        """SELECT r.id AS registration_id, s.id AS student_id, s.name, s.roll_number,
                  s.status, e.id AS exam_id, e.course_code, e.title,
                  e.starts_at, e.ends_at, e.room
           FROM registrations r
           JOIN students s ON s.id=r.student_id
           JOIN exams e ON e.id=r.exam_id
           WHERE r.id=?""", (registration_id,)
    ).fetchone()
    if row is None:
        raise ValueError("registration not found")
    return dict(row)


def admit_card(db, registration_id):
    registration = get_registration(db, registration_id)
    if registration["status"] != "active":
        raise ValueError("admit card is only available for an active student")
    return registration


def init_app(app):
    from flask import render_template, request, redirect, url_for, flash
    @app.get("/registrations")
    def index():
        from .students import list_students
        from .exams import list_exams
        return render_template("registrations.html",
                               students=list_students(get_db_for_app()),
                               exams=list_exams(get_db_for_app()))

    @app.post("/registrations")
    def register():
        register_student_for_exam(get_db_for_app(), int(request.form["student_id"]),
                                  int(request.form["exam_id"]))
        flash("Student registered for examination.")
        return redirect(url_for("registrations.index"))

    @app.get("/registrations/<int:registration_id>/admit-card")
    def admit_card_view(registration_id):
        return render_template("admit_card.html", card=admit_card(get_db_for_app(), registration_id))

def get_db_for_app():
    from .web import get_db
    return get_db()
