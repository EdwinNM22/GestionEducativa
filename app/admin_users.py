from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for

from .auth import login_required, role_required
from .extensions import db
from .models import ROLE_ADMIN, ROLE_STUDENT, ROLE_TEACHER, ROLES, Student, Teacher, User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
DEFAULT_PER_PAGE = 25
MAX_PER_PAGE = 100


ROLE_LABELS = {
    ROLE_ADMIN: "Administrador",
    ROLE_TEACHER: "Profesor",
    ROLE_STUDENT: "Estudiante",
}


def _pagination_args():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=DEFAULT_PER_PAGE, type=int)
    if page is None or page < 1:
        page = 1
    if per_page is None or per_page < 1:
        per_page = DEFAULT_PER_PAGE
    per_page = min(per_page, MAX_PER_PAGE)
    return page, per_page


def _try_create_user():
    """Crea usuario desde request.form. Retorna (User|None, mensaje_error|None)."""
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "").strip()

    if not username or not email or not password or role not in ROLES:
        return None, "Completa todos los campos con un rol valido."

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return None, "Ya existe un usuario con ese nombre o correo."

    user = User(username=username, email=email, role=role)
    err = _sync_user_profile_link(user, role, email, username)
    if err:
        return None, err

    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user, None


def _sync_user_profile_link(user: User, role: str, email: str, username: str):
    if role == ROLE_ADMIN:
        user.student_id = None
        user.teacher_id = None
        return None

    if role == ROLE_STUDENT:
        student = Student.query.filter_by(email=email).first()
        if student is None:
            student = Student(full_name=username, email=email)
            db.session.add(student)
            db.session.flush()
        owner = User.query.filter_by(student_id=student.id).first()
        if owner and owner.id != user.id:
            return "Ya existe una cuenta de usuario para este estudiante."
        user.student_id = student.id
        user.teacher_id = None
        return None

    teacher = Teacher.query.filter_by(email=email).first()
    if teacher is None:
        teacher = Teacher(full_name=username, email=email)
        db.session.add(teacher)
        db.session.flush()
    owner = User.query.filter_by(teacher_id=teacher.id).first()
    if owner and owner.id != user.id:
        return "Ya existe una cuenta de usuario para este profesor."
    user.teacher_id = teacher.id
    user.student_id = None
    return None


@admin_bp.route("/usuarios", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def users_list():
    if request.method == "POST":
        user, err = _try_create_user()
        wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        if err:
            if wants_json:
                return jsonify({"ok": False, "error": err}), 400
            flash(err, "error")
            return redirect(url_for("admin.users_list"))

        if wants_json:
            return jsonify(
                {
                    "ok": True,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "role": user.role,
                        "role_label": ROLE_LABELS.get(user.role, user.role),
                    },
                    "delete_url": url_for("admin.delete_user", user_id=user.id),
                }
            )

        flash("Usuario creado.", "success")
        return redirect(url_for("admin.users_list"))

    page, per_page = _pagination_args()
    users_pagination = User.query.order_by(User.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template(
        "admin/users.html",
        users=users_pagination.items,
        users_pagination=users_pagination,
        roles=ROLES,
        role_labels=ROLE_LABELS,
    )


@admin_bp.route("/usuarios/<int:user_id>/editar", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "").strip()
    password = request.form.get("password", "")
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if not username or not email or role not in ROLES:
        msg = "Usuario, correo y rol son obligatorios."
        if wants_json:
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg, "error")
        return redirect(url_for("admin.users_list"))

    duplicate = User.query.filter(
        ((User.username == username) | (User.email == email)) & (User.id != user.id)
    ).first()
    if duplicate:
        msg = "Ya existe otro usuario con ese nombre o correo."
        if wants_json:
            return jsonify({"ok": False, "error": msg}), 400
        flash(msg, "error")
        return redirect(url_for("admin.users_list"))

    user.username = username
    user.email = email
    user.role = role
    err = _sync_user_profile_link(user, role, email, username)
    if err:
        db.session.rollback()
        if wants_json:
            return jsonify({"ok": False, "error": err}), 400
        flash(err, "error")
        return redirect(url_for("admin.users_list"))

    if password:
        user.set_password(password)

    db.session.commit()

    if wants_json:
        return jsonify(
            {
                "ok": True,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "role_label": ROLE_LABELS.get(user.role, user.role),
                },
            }
        )

    flash("Usuario actualizado.", "success")
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/usuarios/<int:user_id>/eliminar", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == g.user.id:
        flash("No puedes eliminar tu propia cuenta.", "error")
        return redirect(url_for("admin.users_list"))

    db.session.delete(user)
    db.session.commit()
    flash("Usuario eliminado.", "success")
    return redirect(url_for("admin.users_list"))
