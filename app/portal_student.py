from flask import Blueprint, flash, g, render_template, request

from .auth import login_required, role_required
from .grading import PASSING_GRADE
from .models import ROLE_STUDENT, Enrollment

alumno_bp = Blueprint("alumno", __name__, url_prefix="/alumno")
DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 100


@alumno_bp.route("/")
@login_required
@role_required(ROLE_STUDENT)
def panel():
    if g.user.student_id is None:
        flash(
            "Tu cuenta no esta vinculada a un perfil de estudiante. Contacta al administrador.",
            "error",
        )
        return render_template("alumno/panel.html", enrollments=[], passing_grade=PASSING_GRADE)

    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=DEFAULT_PER_PAGE, type=int)
    if page is None or page < 1:
        page = 1
    if per_page is None or per_page < 1:
        per_page = DEFAULT_PER_PAGE
    per_page = min(per_page, MAX_PER_PAGE)

    enrollments_pagination = (
        Enrollment.query.filter_by(student_id=g.user.student_id)
        .order_by(Enrollment.id.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return render_template(
        "alumno/panel.html",
        enrollments=enrollments_pagination.items,
        enrollments_pagination=enrollments_pagination,
        passing_grade=PASSING_GRADE,
    )
