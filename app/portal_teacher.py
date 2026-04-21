from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .auth import login_required, role_required
from .extensions import db
from .grading import parse_grade
from .models import ROLE_TEACHER, Enrollment, Subject

profesor_bp = Blueprint("profesor", __name__, url_prefix="/profesor")


def _teacher_subject_or_404(subject_id: int) -> Subject:
    if g.user.teacher_id is None:
        abort(403)
    subj = Subject.query.get_or_404(subject_id)
    if subj.teacher_id != g.user.teacher_id:
        abort(403)
    return subj


@profesor_bp.route("/")
@login_required
@role_required(ROLE_TEACHER)
def panel():
    if g.user.teacher_id is None:
        flash(
            "Tu cuenta no esta vinculada a un perfil de profesor. Contacta al administrador.",
            "error",
        )
        return render_template("profesor/panel.html", subjects=[])

    subjects = (
        Subject.query.filter_by(teacher_id=g.user.teacher_id).order_by(Subject.name.asc()).all()
    )
    return render_template("profesor/panel.html", subjects=subjects)


@profesor_bp.route("/materia/<int:subject_id>", methods=["GET", "POST"])
@login_required
@role_required(ROLE_TEACHER)
def materia_detail(subject_id):
    subject = _teacher_subject_or_404(subject_id)

    if request.method == "POST":
        raw_id = request.form.get("enrollment_id", "").strip()
        if not raw_id:
            flash("Solicitud invalida.", "error")
            return redirect(url_for("profesor.materia_detail", subject_id=subject_id))

        enrollment = Enrollment.query.get_or_404(int(raw_id))
        if enrollment.subject_id != subject.id:
            abort(403)

        lab1 = parse_grade(request.form.get("lab1"))
        lab2 = parse_grade(request.form.get("lab2"))
        partial = parse_grade(request.form.get("partial"))
        if None in (lab1, lab2, partial):
            flash("Las notas deben estar entre 0 y 10.", "error")
            return redirect(url_for("profesor.materia_detail", subject_id=subject_id))

        enrollment.lab1 = lab1
        enrollment.lab2 = lab2
        enrollment.partial = partial
        db.session.commit()
        flash("Notas actualizadas.", "success")
        return redirect(url_for("profesor.materia_detail", subject_id=subject_id))

    enrollments = (
        Enrollment.query.filter_by(subject_id=subject.id).order_by(Enrollment.id.asc()).all()
    )
    return render_template(
        "profesor/materia.html",
        subject=subject,
        enrollments=enrollments,
    )
