from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


ROLE_ADMIN = "admin"
ROLE_TEACHER = "teacher"
ROLE_STUDENT = "student"
ROLES = (ROLE_ADMIN, ROLE_TEACHER, ROLE_STUDENT)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_STUDENT)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True, unique=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=True, unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    student = db.relationship("Student", foreign_keys=[student_id])
    teacher = db.relationship("Teacher", foreign_keys=[teacher_id])

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    enrollments = db.relationship(
        "Enrollment", back_populates="student", cascade="all, delete-orphan"
    )


class Teacher(db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    subjects = db.relationship("Subject", back_populates="teacher")


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    section = db.Column(db.String(1), nullable=False, default="A")
    code = db.Column(db.String(20), unique=True, nullable=False)
    image_path = db.Column(db.String(255), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    teacher = db.relationship("Teacher", back_populates="subjects")
    enrollments = db.relationship(
        "Enrollment", back_populates="subject", cascade="all, delete-orphan"
    )


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    __table_args__ = (
        db.UniqueConstraint("student_id", "subject_id", name="uq_student_subject"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    lab1 = db.Column(db.Float, nullable=False, default=0.0)
    lab2 = db.Column(db.Float, nullable=False, default=0.0)
    partial = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    student = db.relationship("Student", back_populates="enrollments")
    subject = db.relationship("Subject", back_populates="enrollments")

    @property
    def final_grade(self):
        return round((self.lab1 * 0.25) + (self.lab2 * 0.25) + (self.partial * 0.50), 2)
