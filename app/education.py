from datetime import datetime
import os
import re

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from .auth import login_required, role_required
from .extensions import db
from .grading import parse_grade
from .models import ROLE_ADMIN, ROLE_TEACHER, Enrollment, Student, Subject, Teacher, User

education_bp = Blueprint("education", __name__)
DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 100


def _pagination_args():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=DEFAULT_PER_PAGE, type=int)
    if page is None or page < 1:
        page = 1
    if per_page is None or per_page < 1:
        per_page = DEFAULT_PER_PAGE
    per_page = min(per_page, MAX_PER_PAGE)
    return page, per_page


def _slug3(text: str) -> str:
    letters = re.sub(r"[^A-Za-z]", "", text or "").upper()
    if len(letters) >= 3:
        return letters[:3]
    return (letters + "XXX")[:3]


def _generate_subject_code(name: str, year: int | None = None) -> str:
    y = year or datetime.now().year
    base = f"{_slug3(name)}{y}"
    candidate = base
    n = 1
    while Subject.query.filter_by(code=candidate).first():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def _save_subject_image(file_storage, subject_name: str) -> str | None:
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None
    filename = secure_filename(file_storage.filename)
    if not filename:
        return None
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    slug = _slug3(subject_name)
    final_name = f"{slug}_{stamp}{ext}"
    folder = current_app.config["SUBJECT_IMAGE_UPLOAD_DIR"]
    os.makedirs(folder, exist_ok=True)
    file_storage.save(os.path.join(folder, final_name))
    return f"uploads/subjects/{final_name}"


@education_bp.route("/estudiantes", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN)
def students():
    page, per_page = _pagination_args()
    students_pagination = Student.query.order_by(Student.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template(
        "students.html",
        students=students_pagination.items,
        students_pagination=students_pagination,
    )


@education_bp.route("/estudiantes/<int:student_id>/editar", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    if not full_name or not email:
        flash("Nombre y correo son obligatorios.", "error")
        return redirect(url_for("education.students"))

    existing = Student.query.filter(Student.email == email, Student.id != student.id).first()
    if existing:
        flash("Ese correo ya esta en uso.", "error")
        return redirect(url_for("education.students"))

    student.full_name = full_name
    student.email = email
    db.session.commit()
    flash("Estudiante actualizado.", "success")
    return redirect(url_for("education.students"))


@education_bp.route("/estudiantes/<int:student_id>/eliminar", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def delete_student(student_id):
    if User.query.filter_by(student_id=student_id).first():
        flash("Este estudiante tiene una cuenta de usuario. Elimina o reasigna ese usuario primero.", "error")
        return redirect(url_for("education.students"))
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash("Estudiante eliminado.", "success")
    return redirect(url_for("education.students"))


@education_bp.route("/estudiantes/<int:student_id>/materias", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN)
def student_subjects(student_id):
    student = Student.query.get_or_404(student_id)
    rows = (
        db.session.query(
            Subject.id.label("subject_id"),
            Subject.name.label("subject_name"),
            Teacher.full_name.label("teacher_name"),
        )
        .join(Enrollment, Enrollment.subject_id == Subject.id)
        .outerjoin(Teacher, Teacher.id == Subject.teacher_id)
        .filter(Enrollment.student_id == student.id)
        .order_by(Subject.name.asc())
        .all()
    )
    return jsonify(
        {
            "ok": True,
            "student": {"id": student.id, "full_name": student.full_name},
            "subjects": [
                {
                    "id": row.subject_id,
                    "name": row.subject_name,
                    "teacher_name": row.teacher_name or "Sin asignar",
                }
                for row in rows
            ],
        }
    )


@education_bp.route("/estudiantes/<int:student_id>/asignar-materias", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def assign_student_subjects(student_id):
    student = Student.query.get_or_404(student_id)

    if request.method == "GET":
        assigned_ids = {
            e.subject_id for e in Enrollment.query.with_entities(Enrollment.subject_id).filter_by(student_id=student.id).all()
        }
        subjects = Subject.query.order_by(Subject.name.asc()).all()
        return jsonify(
            {
                "ok": True,
                "student": {"id": student.id, "full_name": student.full_name},
                "subjects": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "assigned": s.id in assigned_ids,
                    }
                    for s in subjects
                ],
            }
        )

    data = request.get_json(silent=True) or {}
    raw_ids = data.get("subject_ids", [])
    if not isinstance(raw_ids, list):
        return jsonify({"ok": False, "error": "Lista de materias invalida."}), 400

    try:
        selected_ids = {int(v) for v in raw_ids}
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "IDs de materias invalidos."}), 400

    if not selected_ids:
        return jsonify({"ok": False, "error": "Selecciona al menos una materia."}), 400

    valid_ids = {
        sid
        for (sid,) in db.session.query(Subject.id).filter(Subject.id.in_(selected_ids)).all()
    }
    if len(valid_ids) != len(selected_ids):
        return jsonify({"ok": False, "error": "Algunas materias no existen."}), 400

    existing_ids = {
        e.subject_id
        for e in Enrollment.query.with_entities(Enrollment.subject_id).filter_by(student_id=student.id).all()
    }
    new_ids = valid_ids - existing_ids
    for subject_id in new_ids:
        db.session.add(Enrollment(student_id=student.id, subject_id=subject_id))
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "added": len(new_ids),
            "message": f"Se asignaron {len(new_ids)} materias nuevas.",
        }
    )


@education_bp.route("/estudiantes/<int:student_id>/materias/<int:subject_id>/notas", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN)
def student_subject_grades(student_id, subject_id):
    student = Student.query.get_or_404(student_id)
    subject = Subject.query.get_or_404(subject_id)
    enrollments = (
        Enrollment.query.filter_by(student_id=student.id, subject_id=subject.id)
        .order_by(Enrollment.id.desc())
        .all()
    )
    return jsonify(
        {
            "ok": True,
            "student": {"id": student.id, "full_name": student.full_name},
            "subject": {"id": subject.id, "name": subject.name},
            "grades": [
                {
                    "id": e.id,
                    "lab1": e.lab1,
                    "lab2": e.lab2,
                    "partial": e.partial,
                    "final_grade": e.final_grade,
                }
                for e in enrollments
            ],
        }
    )


@education_bp.route("/profesores", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN)
def teachers():
    page, per_page = _pagination_args()
    teachers_pagination = Teacher.query.order_by(Teacher.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template(
        "teachers.html",
        teachers=teachers_pagination.items,
        teachers_pagination=teachers_pagination,
    )


@education_bp.route("/profesores/<int:teacher_id>/asignar-materias", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def assign_teacher_subjects(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)

    if request.method == "GET":
        subjects = Subject.query.order_by(Subject.name.asc()).all()
        return jsonify(
            {
                "ok": True,
                "teacher": {"id": teacher.id, "full_name": teacher.full_name},
                "subjects": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "assigned": s.teacher_id == teacher.id,
                        "current_teacher": s.teacher.full_name if s.teacher else None,
                    }
                    for s in subjects
                ],
            }
        )

    data = request.get_json(silent=True) or {}
    raw_ids = data.get("subject_ids", [])
    if not isinstance(raw_ids, list):
        return jsonify({"ok": False, "error": "Lista de materias invalida."}), 400

    try:
        selected_ids = {int(v) for v in raw_ids}
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "IDs de materias invalidos."}), 400

    if not selected_ids:
        return jsonify({"ok": False, "error": "Selecciona al menos una materia."}), 400

    selected_subjects = Subject.query.filter(Subject.id.in_(selected_ids)).all()
    if len(selected_subjects) != len(selected_ids):
        return jsonify({"ok": False, "error": "Algunas materias no existen."}), 400

    changed = 0
    for subject in selected_subjects:
        if subject.teacher_id != teacher.id:
            subject.teacher_id = teacher.id
            changed += 1
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "changed": changed,
            "message": f"Se asignaron {changed} materias al profesor.",
        }
    )


@education_bp.route("/profesores/<int:teacher_id>/editar", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def edit_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    if not full_name or not email:
        flash("Nombre y correo son obligatorios.", "error")
        return redirect(url_for("education.teachers"))

    existing = Teacher.query.filter(Teacher.email == email, Teacher.id != teacher.id).first()
    if existing:
        flash("Ese correo ya esta en uso.", "error")
        return redirect(url_for("education.teachers"))

    teacher.full_name = full_name
    teacher.email = email
    db.session.commit()
    flash("Profesor actualizado.", "success")
    return redirect(url_for("education.teachers"))


@education_bp.route("/profesores/<int:teacher_id>/eliminar", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def delete_teacher(teacher_id):
    if User.query.filter_by(teacher_id=teacher_id).first():
        flash("Este profesor tiene una cuenta de usuario. Elimina o reasigna ese usuario primero.", "error")
        return redirect(url_for("education.teachers"))
    teacher = Teacher.query.get_or_404(teacher_id)
    for subject in teacher.subjects:
        subject.teacher_id = None
    db.session.delete(teacher)
    db.session.commit()
    flash("Profesor eliminado.", "success")
    return redirect(url_for("education.teachers"))


@education_bp.route("/materias", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def subjects():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        section = request.form.get("section", "A").strip().upper()
        teacher_id = request.form.get("teacher_id", "").strip()
        image_file = request.files.get("image")

        if not name:
            flash("El nombre de la materia es obligatorio.", "error")
            return redirect(url_for("education.subjects"))

        if section not in {"A", "B", "C"}:
            flash("La seccion debe ser A, B o C.", "error")
            return redirect(url_for("education.subjects"))

        if Subject.query.filter_by(name=name, section=section).first():
            flash("Ya existe una materia con ese nombre y seccion.", "error")
            return redirect(url_for("education.subjects"))

        code = _generate_subject_code(name)
        teacher = Teacher.query.get(int(teacher_id)) if teacher_id else None
        image_path = _save_subject_image(image_file, name)
        db.session.add(
            Subject(name=name, section=section, code=code, teacher=teacher, image_path=image_path)
        )
        db.session.commit()
        flash("Materia creada correctamente.", "success")
        return redirect(url_for("education.subjects"))

    page, per_page = _pagination_args()
    subjects_pagination = Subject.query.order_by(Subject.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    teachers_list = Teacher.query.order_by(Teacher.full_name.asc()).all()
    return render_template(
        "subjects.html",
        subjects=subjects_pagination.items,
        teachers=teachers_list,
        subjects_pagination=subjects_pagination,
    )


@education_bp.route("/materias/<int:subject_id>/profesores", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN)
def subject_teachers(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    teachers = []
    if subject.teacher:
        teachers.append(
            {
                "id": subject.teacher.id,
                "full_name": subject.teacher.full_name,
                "email": subject.teacher.email,
            }
        )
    return jsonify(
        {
            "ok": True,
            "subject": {
                "id": subject.id,
                "name": subject.name,
                "section": subject.section,
                "code": subject.code,
                "image_path": subject.image_path,
            },
            "teachers": teachers,
        }
    )


@education_bp.route("/materias/<int:subject_id>/estudiantes", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN)
def subject_students(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    rows = (
        db.session.query(Student.id, Student.full_name, Student.email)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .filter(Enrollment.subject_id == subject.id)
        .order_by(Student.full_name.asc())
        .all()
    )
    return jsonify(
        {
            "ok": True,
            "subject": {
                "id": subject.id,
                "name": subject.name,
                "section": subject.section,
                "code": subject.code,
                "image_path": subject.image_path,
            },
            "students": [
                {"id": r.id, "full_name": r.full_name, "email": r.email}
                for r in rows
            ],
        }
    )


@education_bp.route("/materias/<int:subject_id>/editar", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    name = request.form.get("name", "").strip()
    section = request.form.get("section", subject.section).strip().upper()
    teacher_id = request.form.get("teacher_id", "").strip()

    if not name:
        flash("El nombre de la materia es obligatorio.", "error")
        return redirect(url_for("education.subjects"))

    if section not in {"A", "B", "C"}:
        flash("La seccion debe ser A, B o C.", "error")
        return redirect(url_for("education.subjects"))

    existing = Subject.query.filter(
        Subject.name == name, Subject.section == section, Subject.id != subject.id
    ).first()
    if existing:
        flash("Ese nombre de materia ya existe en esa seccion.", "error")
        return redirect(url_for("education.subjects"))

    subject.name = name
    subject.section = section
    subject.teacher_id = int(teacher_id) if teacher_id else None
    db.session.commit()
    flash("Materia actualizada.", "success")
    return redirect(url_for("education.subjects"))


@education_bp.route("/materias/<int:subject_id>/imagen", methods=["POST"])
@login_required
def update_subject_image(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if g.user.role == ROLE_TEACHER:
        if g.user.teacher_id is None or subject.teacher_id != g.user.teacher_id:
            abort(403)
    elif g.user.role != ROLE_ADMIN:
        abort(403)

    image_file = request.files.get("image")
    image_path = _save_subject_image(image_file, subject.name)
    if not image_path:
        flash("Imagen invalida. Usa PNG, JPG, JPEG o WEBP.", "error")
        return redirect(request.referrer or url_for("education.subjects"))

    subject.image_path = image_path
    db.session.commit()
    flash("Imagen de materia actualizada.", "success")
    return redirect(request.referrer or url_for("education.subjects"))


@education_bp.route("/materias/<int:subject_id>/eliminar", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    db.session.delete(subject)
    db.session.commit()
    flash("Materia eliminada.", "success")
    return redirect(url_for("education.subjects"))


@education_bp.route("/notas", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def grades():
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        subject_id = request.form.get("subject_id", "").strip()
        lab1 = parse_grade(request.form.get("lab1"))
        lab2 = parse_grade(request.form.get("lab2"))
        partial = parse_grade(request.form.get("partial"))

        if not student_id or not subject_id or None in (lab1, lab2, partial):
            flash("Completa todos los campos y usa notas entre 0 y 10.", "error")
            return redirect(url_for("education.grades"))

        enrollment = Enrollment.query.filter_by(
            student_id=int(student_id), subject_id=int(subject_id)
        ).first()
        if not enrollment:
            flash("Ese alumno no esta asignado a esa materia.", "error")
            return redirect(url_for("education.grades"))

        enrollment.lab1 = lab1
        enrollment.lab2 = lab2
        enrollment.partial = partial
        db.session.commit()
        flash("Notas guardadas correctamente.", "success")
        return redirect(url_for("education.grades"))

    page, per_page = _pagination_args()
    enrollments_pagination = Enrollment.query.order_by(Enrollment.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    students_list = Student.query.order_by(Student.full_name.asc()).all()
    subjects_list = Subject.query.order_by(Subject.name.asc()).all()
    return render_template(
        "grades.html",
        enrollments=enrollments_pagination.items,
        students=students_list,
        subjects=subjects_list,
        enrollments_pagination=enrollments_pagination,
    )


@education_bp.route("/notas/<int:enrollment_id>/editar", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def edit_grade(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    lab1 = parse_grade(request.form.get("lab1"))
    lab2 = parse_grade(request.form.get("lab2"))
    partial = parse_grade(request.form.get("partial"))
    if None in (lab1, lab2, partial):
        flash("Las notas deben estar entre 0 y 10.", "error")
        return redirect(url_for("education.grades"))

    enrollment.lab1 = lab1
    enrollment.lab2 = lab2
    enrollment.partial = partial
    db.session.commit()
    flash("Notas actualizadas.", "success")
    return redirect(url_for("education.grades"))


@education_bp.route("/notas/<int:enrollment_id>/eliminar", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def delete_grade(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    db.session.delete(enrollment)
    db.session.commit()
    flash("Registro de notas eliminado.", "success")
    return redirect(url_for("education.grades"))
