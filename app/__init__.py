import os

import click
from flask import Flask, g, session
from dotenv import load_dotenv
from flask_migrate import upgrade

from .extensions import db, migrate
from .models import ROLE_ADMIN, User


def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:password@localhost:3306/gestion-educativa-db",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SUBJECT_IMAGE_UPLOAD_DIR"] = os.path.join(
        app.root_path, "static", "uploads", "subjects"
    )
    os.makedirs(app.config["SUBJECT_IMAGE_UPLOAD_DIR"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    with app.app_context():
        # Aplica cambios de esquema pendientes al arrancar.
        upgrade()
        # Crea tablas faltantes si aun no existen.
        db.create_all()

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        g.user = User.query.get(user_id) if user_id else None

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        print("Base de datos inicializada.")

    from .routes import main_bp
    from .auth import auth_bp
    from .admin_users import admin_bp
    from .education import education_bp
    from .analytics import analytics_bp
    from .portal_student import alumno_bp
    from .portal_teacher import profesor_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(education_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(alumno_bp)
    app.register_blueprint(profesor_bp)

    @app.cli.command("set-admin")
    @click.argument("email", required=False)
    def set_admin_cmd(email):
        """Asigna rol admin: flask set-admin [email]. Sin email usa el primer usuario por id."""
        if email:
            u = User.query.filter_by(email=email.strip().lower()).first()
            if not u:
                print("Usuario no encontrado.")
                return
        else:
            u = User.query.order_by(User.id.asc()).first()
            if not u:
                print("No hay usuarios.")
                return
        u.role = ROLE_ADMIN
        u.student_id = None
        u.teacher_id = None
        db.session.commit()
        print(f"Usuario {u.email} es ahora admin.")

    return app
