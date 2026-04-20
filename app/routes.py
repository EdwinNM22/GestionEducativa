from flask import Blueprint, g, redirect, render_template, url_for

from .auth import login_required
from .models import Enrollment, Student, Subject, Teacher

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    if g.user is None:
        return redirect(url_for("auth.login"))
    return redirect(url_for("main.dashboard"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    stats = {
        "students": Student.query.count(),
        "teachers": Teacher.query.count(),
        "subjects": Subject.query.count(),
        "grades": Enrollment.query.count(),
    }
    latest_grades = Enrollment.query.order_by(Enrollment.id.desc()).limit(5).all()
    return render_template(
        "dashboard.html", user=g.user, stats=stats, latest_grades=latest_grades
    )
