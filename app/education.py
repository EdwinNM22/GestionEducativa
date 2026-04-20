from flask import Blueprint, flash, redirect, render_template, request, url_for

from .auth import login_required
from .extensions import db
from .models import Enrollment, Student, Subject, Teacher

education_bp = Blueprint("education", __name__)


def parse_grade(value):
    try:
        grade = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= grade <= 10:
        return grade
    return None


@education_bp.route("/estudiantes", methods=["GET", "POST"])
@login_required
def students():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        if not full_name or not email:
            flash("Nombre y correo son obligatorios.", "error")
            return redirect(url_for("education.students"))

        if Student.query.filter_by(email=email).first():
            flash("Ya existe un estudiante con ese correo.", "error")
            return redirect(url_for("education.students"))

        db.session.add(Student(full_name=full_name, email=email))
        db.session.commit()
        flash("Estudiante creado correctamente.", "success")
        return redirect(url_for("education.students"))

    students_list = Student.query.order_by(Student.id.desc()).all()
    return render_template("students.html", students=students_list)


@education_bp.route("/estudiantes/<int:student_id>/editar", methods=["POST"])
@login_required
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
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash("Estudiante eliminado.", "success")
    return redirect(url_for("education.students"))


@education_bp.route("/profesores", methods=["GET", "POST"])
@login_required
def teachers():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        if not full_name or not email:
            flash("Nombre y correo son obligatorios.", "error")
            return redirect(url_for("education.teachers"))

        if Teacher.query.filter_by(email=email).first():
            flash("Ya existe un profesor con ese correo.", "error")
            return redirect(url_for("education.teachers"))

        db.session.add(Teacher(full_name=full_name, email=email))
        db.session.commit()
        flash("Profesor creado correctamente.", "success")
        return redirect(url_for("education.teachers"))

    teachers_list = Teacher.query.order_by(Teacher.id.desc()).all()
    return render_template("teachers.html", teachers=teachers_list)


@education_bp.route("/profesores/<int:teacher_id>/editar", methods=["POST"])
@login_required
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
def delete_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    for subject in teacher.subjects:
        subject.teacher_id = None
    db.session.delete(teacher)
    db.session.commit()
    flash("Profesor eliminado.", "success")
    return redirect(url_for("education.teachers"))


@education_bp.route("/materias", methods=["GET", "POST"])
@login_required
def subjects():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        teacher_id = request.form.get("teacher_id", "").strip()

        if not name:
            flash("El nombre de la materia es obligatorio.", "error")
            return redirect(url_for("education.subjects"))

        if Subject.query.filter_by(name=name).first():
            flash("Ya existe una materia con ese nombre.", "error")
            return redirect(url_for("education.subjects"))

        teacher = Teacher.query.get(int(teacher_id)) if teacher_id else None
        db.session.add(Subject(name=name, teacher=teacher))
        db.session.commit()
        flash("Materia creada correctamente.", "success")
        return redirect(url_for("education.subjects"))

    subjects_list = Subject.query.order_by(Subject.id.desc()).all()
    teachers_list = Teacher.query.order_by(Teacher.full_name.asc()).all()
    return render_template(
        "subjects.html", subjects=subjects_list, teachers=teachers_list
    )


@education_bp.route("/materias/<int:subject_id>/editar", methods=["POST"])
@login_required
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    name = request.form.get("name", "").strip()
    teacher_id = request.form.get("teacher_id", "").strip()

    if not name:
        flash("El nombre de la materia es obligatorio.", "error")
        return redirect(url_for("education.subjects"))

    existing = Subject.query.filter(Subject.name == name, Subject.id != subject.id).first()
    if existing:
        flash("Ese nombre de materia ya existe.", "error")
        return redirect(url_for("education.subjects"))

    subject.name = name
    subject.teacher_id = int(teacher_id) if teacher_id else None
    db.session.commit()
    flash("Materia actualizada.", "success")
    return redirect(url_for("education.subjects"))


@education_bp.route("/materias/<int:subject_id>/eliminar", methods=["POST"])
@login_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    db.session.delete(subject)
    db.session.commit()
    flash("Materia eliminada.", "success")
    return redirect(url_for("education.subjects"))


@education_bp.route("/notas", methods=["GET", "POST"])
@login_required
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

        existing = Enrollment.query.filter_by(
            student_id=int(student_id), subject_id=int(subject_id)
        ).first()
        if existing:
            flash("Ese estudiante ya tiene notas para esa materia.", "error")
            return redirect(url_for("education.grades"))

        enrollment = Enrollment(
            student_id=int(student_id),
            subject_id=int(subject_id),
            lab1=lab1,
            lab2=lab2,
            partial=partial,
        )
        db.session.add(enrollment)
        db.session.commit()
        flash("Notas guardadas correctamente.", "success")
        return redirect(url_for("education.grades"))

    enrollments = Enrollment.query.order_by(Enrollment.id.desc()).all()
    students_list = Student.query.order_by(Student.full_name.asc()).all()
    subjects_list = Subject.query.order_by(Subject.name.asc()).all()
    return render_template(
        "grades.html",
        enrollments=enrollments,
        students=students_list,
        subjects=subjects_list,
    )


@education_bp.route("/notas/<int:enrollment_id>/editar", methods=["POST"])
@login_required
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
def delete_grade(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    db.session.delete(enrollment)
    db.session.commit()
    flash("Registro de notas eliminado.", "success")
    return redirect(url_for("education.grades"))
