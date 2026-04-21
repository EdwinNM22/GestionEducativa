#!/usr/bin/env python3
"""
Genera un archivo .sql (MySQL) con datos de prueba usando Faker.
Uso:
  pip install faker werkzeug
  python generate_seed.py
  python generate_seed.py --students 6000 --target-rows 20000

Por defecto ~20k filas totales: muchos estudiantes y enrollments (notas),
pocos profesores y materias realistas.
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime
from pathlib import Path

from faker import Faker
from werkzeug.security import generate_password_hash

# --- Config por defecto (ajusta totales ~20k filas) ---
DEFAULT_TEACHERS = 45
DEFAULT_SUBJECTS = 55
DEFAULT_STUDENTS = 4200
# enrollments = target_total - teachers - subjects - students
DEFAULT_TARGET_TOTAL_ROWS = 20_000

SUBJECT_NAME_POOL = [
    "Matematica I",
    "Matematica II",
    "Programacion I",
    "Programacion II",
    "Base de Datos",
    "Redes",
    "Sistemas Operativos",
    "Fisica I",
    "Fisica II",
    "Quimica General",
    "Literatura",
    "Historia",
    "Ingles I",
    "Ingles II",
    "Metodologia de la Investigacion",
    "Estadistica",
    "Calculo I",
    "Calculo II",
    "Algebra Lineal",
    "Estructuras de Datos",
    "Ingenieria de Software",
    "Inteligencia Artificial",
    "Seguridad Informatica",
    "Electronica",
    "Proyecto Final",
    "Etica Profesional",
    "Economia",
    "Administracion",
    "Contabilidad",
    "Derecho Informatico",
    "Comunicacion Oral y Escrita",
    "Laboratorio Programacion",
    "Laboratorio Redes",
    "Arquitectura de Computadoras",
    "Compiladores",
    "Graficos por Computadora",
    "Probabilidad",
    "Investigacion de Operaciones",
    "Fundamentos de Web",
    "Desarrollo Movil",
    "Cloud Computing",
    "DevOps",
    "Testing de Software",
    "UX/UI",
    "Gestion de Proyectos",
    "Finanzas",
    "Microeconomia",
    "Macroeconomia",
    "Psicologia Organizacional",
    "Recursos Humanos",
    "Marketing",
    "Logica",
    "Diseno de Algoritmos",
    "Teoria de la Computacion",
    "Sistemas Distribuidos",
    "Bases de Datos Avanzadas",
    "Minería de Datos",
    "Big Data",
    "IoT",
    "Blockchain",
]


def sql_str(value: str | None) -> str:
    if value is None:
        return "NULL"
    escaped = str(value).replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def sql_float(x: float) -> str:
    return f"{float(x):.2f}"


def random_created_at_2026() -> str:
    """Genera fechas aleatorias en 2026 (mes no uniforme exacto)."""
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    hour = random.randint(7, 21)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return f"2026-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"


def clamp_grade(value: float) -> float:
    return max(0.0, min(10.0, round(value, 2)))


def enrollment_grades(student_skill: float, subject_difficulty: float) -> tuple[float, float, float]:
    """Notas con alta variación: mezcla de talento, dificultad y ruido."""
    base = 6.0 + student_skill - subject_difficulty + random.uniform(-1.9, 1.9)
    lab1 = clamp_grade(base + random.uniform(-3.0, 3.0))
    lab2 = clamp_grade(base + random.uniform(-3.0, 3.0))
    partial = clamp_grade(base + random.uniform(-3.6, 3.6))

    # Outliers para que las gráficas no salgan lineales.
    if random.random() < 0.14:
        bump = random.uniform(1.4, 3.6) if random.random() < 0.5 else -random.uniform(1.4, 3.9)
        partial = clamp_grade(partial + bump)
    if random.random() < 0.09:
        lab1 = clamp_grade(lab1 + random.uniform(-3.8, 3.8))
    if random.random() < 0.09:
        lab2 = clamp_grade(lab2 + random.uniform(-3.8, 3.8))

    return lab1, lab2, partial


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera seed_demo.sql para MySQL")
    parser.add_argument("--teachers", type=int, default=DEFAULT_TEACHERS)
    parser.add_argument("--subjects", type=int, default=DEFAULT_SUBJECTS)
    parser.add_argument("--students", type=int, default=DEFAULT_STUDENTS)
    parser.add_argument(
        "--target-rows",
        type=int,
        default=DEFAULT_TARGET_TOTAL_ROWS,
        help="Filas totales aproximadas (teachers+subjects+students+enrollments)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Semilla para reproducibilidad",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "output" / "seed_demo.sql",
    )
    parser.add_argument(
        "--admin-password",
        default="demo123",
        help="Contrasena para usuario admin y profesores (demo)",
    )
    args = parser.parse_args()

    random.seed(args.seed)
    fake = Faker("es_ES")
    Faker.seed(args.seed)

    n_teachers = max(1, args.teachers)
    n_subjects = max(1, args.subjects)
    n_students = max(1, args.students)

    fixed = n_teachers + n_subjects + n_students
    n_enrollments = args.target_rows - fixed
    if n_enrollments < 1:
        raise SystemExit(
            f"target-rows ({args.target_rows}) debe ser mayor que teachers+subjects+students ({fixed})."
        )

    max_possible = n_students * n_subjects
    if n_enrollments > max_possible:
        raise SystemExit(
            f"Se piden {n_enrollments} notas pero solo hay {max_possible} pares unicos "
            f"estudiante-materia posibles. Sube --students o --subjects."
        )

    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)

    pwd_hash = generate_password_hash(args.admin_password)

    subject_names = (SUBJECT_NAME_POOL * ((n_subjects // len(SUBJECT_NAME_POOL)) + 1))[:n_subjects]

    lines: list[str] = []
    lines.append("/* Generated by seed_data/generate_seed.py — MySQL 5.7+ / 8.x, utf8mb4 */")
    lines.append("SET NAMES utf8mb4;")
    lines.append("SET FOREIGN_KEY_CHECKS=0;")
    lines.append("SET UNIQUE_CHECKS=0;")
    lines.append("TRUNCATE TABLE enrollments;")
    lines.append("TRUNCATE TABLE users;")
    lines.append("TRUNCATE TABLE subjects;")
    lines.append("TRUNCATE TABLE students;")
    lines.append("TRUNCATE TABLE teachers;")
    lines.append("SET UNIQUE_CHECKS=1;")
    lines.append("SET FOREIGN_KEY_CHECKS=1;")
    lines.append("")

    # --- teachers ---
    lines.append("-- teachers")
    t_rows: list[str] = []
    teacher_emails: list[str] = []
    for i in range(1, n_teachers + 1):
        name = fake.name()
        email = f"profesor.seed.{i}@demo.local"
        created_at = random_created_at_2026()
        teacher_emails.append(email)
        t_rows.append(f"({i}, {sql_str(name)}, {sql_str(email)}, '{created_at}')")
    lines.append(
        "INSERT INTO teachers (id, full_name, email, created_at) VALUES\n"
        + ",\n".join(t_rows)
        + ";"
    )
    lines.append("")

    # --- students ---
    lines.append("-- students")
    s_rows: list[str] = []
    for i in range(1, n_students + 1):
        name = fake.name()
        email = f"alumno.seed.{i}@demo.local"
        created_at = random_created_at_2026()
        s_rows.append(f"({i}, {sql_str(name)}, {sql_str(email)}, '{created_at}')")
    # Insert por lotes para archivos manejables
    batch = 800
    for start in range(0, len(s_rows), batch):
        chunk = s_rows[start : start + batch]
        lines.append(
            "INSERT INTO students (id, full_name, email, created_at) VALUES\n"
            + ",\n".join(chunk)
            + ";"
        )
    lines.append("")

    # --- subjects (teacher_id ciclico, codigo unico) ---
    lines.append("-- subjects")
    sections = ["A", "B", "C"]
    sub_rows: list[str] = []
    for j in range(1, n_subjects + 1):
        tid = ((j - 1) % n_teachers) + 1
        name = subject_names[j - 1]
        sec = sections[(j - 1) % len(sections)]
        code = f"SUB{j:05d}"
        created_at = random_created_at_2026()
        sub_rows.append(
            f"({j}, {sql_str(name)}, {sql_str(sec)}, {sql_str(code)}, NULL, {tid}, '{created_at}')"
        )
    lines.append(
        "INSERT INTO subjects (id, name, section, code, image_path, teacher_id, created_at) VALUES\n"
        + ",\n".join(sub_rows)
        + ";"
    )
    lines.append("")

    # --- enrollments: muestra aleatoria de pares unicos (student_id, subject_id) ---
    lines.append("-- enrollments (notas)")
    max_pairs = n_students * n_subjects
    if n_enrollments > max_pairs:
        raise SystemExit(
            f"No caben {n_enrollments} enrollments unicos con {n_students} estudiantes y "
            f"{n_subjects} materias (max {max_pairs})."
        )
    all_pairs = [(s, sub) for s in range(1, n_students + 1) for sub in range(1, n_subjects + 1)]
    pairs = random.sample(all_pairs, n_enrollments)
    student_skill = {sid: random.uniform(-2.6, 2.6) for sid in range(1, n_students + 1)}
    subject_difficulty = {subid: random.uniform(-1.8, 1.8) for subid in range(1, n_subjects + 1)}

    e_rows: list[str] = []
    enroll_id = 1
    for s, subj_id in pairs:
        created_at = random_created_at_2026()
        lab1, lab2, partial = enrollment_grades(student_skill[s], subject_difficulty[subj_id])
        e_rows.append(
            f"({enroll_id}, {s}, {subj_id}, {sql_float(lab1)}, {sql_float(lab2)}, {sql_float(partial)}, '{created_at}')"
        )
        enroll_id += 1

    ebatch = 600
    for start in range(0, len(e_rows), ebatch):
        chunk = e_rows[start : start + ebatch]
        lines.append(
            "INSERT INTO enrollments (id, student_id, subject_id, lab1, lab2, partial, created_at) VALUES\n"
            + ",\n".join(chunk)
            + ";"
        )
    lines.append("")

    # --- users: 1 admin + N teachers (mismo password demo) ---
    lines.append("-- users (admin + profesores con login demo)")
    u_rows: list[str] = []
    uid = 1
    admin_created_at = random_created_at_2026()
    u_rows.append(
        f"({uid}, 'admin', 'admin@demo.local', {sql_str(pwd_hash)}, 'admin', NULL, NULL, '{admin_created_at}')"
    )
    uid += 1
    for tid in range(1, n_teachers + 1):
        uname = f"profesor{tid}"
        created_at = random_created_at_2026()
        u_rows.append(
            f"({uid}, {sql_str(uname)}, {sql_str(teacher_emails[tid - 1])}, {sql_str(pwd_hash)}, 'teacher', NULL, {tid}, '{created_at}')"
        )
        uid += 1
    lines.append(
        "INSERT INTO users (id, username, email, password_hash, role, student_id, teacher_id, created_at) VALUES\n"
        + ",\n".join(u_rows)
        + ";"
    )
    lines.append("")

    # Auto increment (por si acaso)
    lines.append("ALTER TABLE teachers AUTO_INCREMENT = " + str(n_teachers + 1) + ";")
    lines.append("ALTER TABLE students AUTO_INCREMENT = " + str(n_students + 1) + ";")
    lines.append("ALTER TABLE subjects AUTO_INCREMENT = " + str(n_subjects + 1) + ";")
    lines.append("ALTER TABLE enrollments AUTO_INCREMENT = " + str(enroll_id) + ";")
    lines.append("ALTER TABLE users AUTO_INCREMENT = " + str(uid) + ";")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    actual_enroll = enroll_id - 1
    total_tablas = n_teachers + n_subjects + n_students + actual_enroll + (1 + n_teachers)
    print(f"Escrito: {out}")
    print(
        f"Resumen: teachers={n_teachers}, subjects={n_subjects}, students={n_students}, "
        f"enrollments={actual_enroll}, users={1 + n_teachers} (admin+profesores)"
    )
    print(
        f"target-rows (solo datos academicos): {n_teachers + n_subjects + n_students + actual_enroll} "
        f"(objetivo {args.target_rows})"
    )
    print(f"Filas insertadas en todas las tablas (incl. users): {total_tablas}")


if __name__ == "__main__":
    main()
