"""Local demonstration interface with form validation and CSRF protection."""
import hmac
import importlib
import importlib.util
import os
from pathlib import Path
import secrets

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

from .db import connect
from .exams import create_exam, list_exams
from .students import create_student, get_student, list_students, set_student_status, update_student


def get_db():
    if "db" not in g:
        from flask import current_app
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("UMS_SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.environ.get("UMS_DATABASE") or str(Path(app.instance_path) / "ums.sqlite"),
        MAX_CONTENT_LENGTH=65536,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            token = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not expected or not token.isascii() or not hmac.compare_digest(token, expected):
                abort(400, description="The form expired. Reload the page and try again.")

    @app.context_processor
    def template_context():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)
        return {"csrf_token": session["csrf_token"], "endpoints": app.view_functions}

    @app.errorhandler(ValueError)
    def validation_error(error):
        return render_template("error.html", message=str(error)), 400

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", message=error.description), 400

    @app.get("/")
    def index():
        return render_template("index.html", students=list_students(get_db()), exams=list_exams(get_db()))

    @app.get("/students")
    def students():
        query = request.args.get("q", "")
        return render_template("students.html", students=list_students(get_db(), query), query=query)

    @app.route("/students/new", methods=["GET", "POST"])
    def student_new():
        if request.method == "POST":
            create_student(get_db(), **{k: request.form.get(k, "") for k in
                           ("roll_number", "name", "email", "programme")})
            flash("Student registered.")
            return redirect(url_for("students"))
        return render_template("student_form.html", student=None)

    @app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
    def student_edit(student_id):
        if request.method == "POST":
            update_student(get_db(), student_id, **{k: request.form.get(k, "") for k in
                           ("name", "email", "programme")})
            flash("Student details updated.")
            return redirect(url_for("students"))
        return render_template("student_form.html", student=get_student(get_db(), student_id))

    @app.post("/students/<int:student_id>/status")
    def student_status(student_id):
        set_student_status(get_db(), student_id, request.form.get("status", ""))
        flash("Student status updated.")
        return redirect(url_for("students"))

    @app.get("/exams")
    def exams():
        date = request.args.get("date", "")
        return render_template("exams.html", exams=list_exams(get_db(), date), date=date)

    @app.route("/exams/new", methods=["GET", "POST"])
    def exam_new():
        if request.method == "POST":
            create_exam(get_db(), **{k: request.form.get(k, "") for k in
                        ("course_code", "title", "starts_at", "ends_at", "room")})
            flash("Examination scheduled.")
            return redirect(url_for("exams"))
        return render_template("exam_form.html")

    # Partner extensions own their services, routes and templates. No placeholder
    # implementation is presented as completed work.
    for module_name in ("ums.fees", "ums.registrations"):
        if importlib.util.find_spec(module_name) is not None:
            module = importlib.import_module(module_name)
            module.init_app(app)
    return app
