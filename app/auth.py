from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from .extensions import db
from .models import ROLE_ADMIN, ROLE_STUDENT, ROLE_TEACHER, User

auth_bp = Blueprint("auth", __name__)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("auth.login"))
            if g.user.role not in allowed_roles:
                flash("No tienes permiso para acceder a esa seccion.", "error")
                return redirect(url_for("main.home"))
            return view(*args, **kwargs)

        return wrapped_view

    return decorator


def home_url_for_user(user: User):
    if user.role == ROLE_ADMIN:
        return url_for("main.dashboard")
    if user.role == ROLE_TEACHER:
        return url_for("profesor.panel")
    if user.role == ROLE_STUDENT:
        return url_for("alumno.panel")
    return url_for("main.dashboard")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not username or not email or not password:
            flash("Completa usuario, correo y contrasena.", "error")
            return render_template("register.html")

        if User.query.filter_by(username=username).first():
            flash("Ese nombre de usuario ya esta en uso.", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("Ese correo ya esta registrado.", "error")
            return render_template("register.html")

        user = User(
            username=username,
            email=email,
            role=ROLE_STUDENT,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Cuenta creada. Ya puedes iniciar sesion.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Credenciales invalidas.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user.id
        return redirect(home_url_for_user(user))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
