import os

from flask import Flask, g, session
from dotenv import load_dotenv

from .extensions import db, migrate
from .models import User


def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:password@localhost:3306/gestion-educativa-db",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    migrate.init_app(app, db)
    with app.app_context():
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
    from .education import education_bp
    from .analytics import analytics_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(education_bp)
    app.register_blueprint(analytics_bp)

    return app
