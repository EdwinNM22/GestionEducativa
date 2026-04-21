from datetime import datetime
from io import BytesIO

import matplotlib
import pandas as pd
import seaborn as sns
from flask import Blueprint, jsonify, redirect, request, send_file, url_for

from .auth import login_required, role_required
from .extensions import db
from .grading import PASSING_GRADE
from .models import ROLE_ADMIN, Enrollment, Student, Subject, Teacher

matplotlib.use("Agg")
import matplotlib.pyplot as plt

analytics_bp = Blueprint("analytics", __name__)


def build_grades_dataframe() -> pd.DataFrame:
    rows = (
        db.session.query(
            Enrollment.id,
            Enrollment.lab1,
            Enrollment.lab2,
            Enrollment.partial,
            Student.full_name.label("student_name"),
            Subject.name.label("subject_name"),
            Teacher.full_name.label("teacher_name"),
        )
        .join(Student, Student.id == Enrollment.student_id)
        .join(Subject, Subject.id == Enrollment.subject_id)
        .outerjoin(Teacher, Teacher.id == Subject.teacher_id)
        .all()
    )

    df = pd.DataFrame(
        [
            {
                "id": row.id,
                "student_name": row.student_name,
                "subject_name": row.subject_name,
                "lab1": row.lab1,
                "lab2": row.lab2,
                "partial": row.partial,
                "teacher_name": row.teacher_name,
            }
            for row in rows
        ]
    )

    if df.empty:
        return df

    df = df.copy()
    df["teacher_name"] = df["teacher_name"].fillna("Sin asignar")
    df["final_grade"] = (
        df["lab1"] * 0.25 + df["lab2"] * 0.25 + df["partial"] * 0.50
    ).round(2)
    return df


def build_students_dataframe() -> pd.DataFrame:
    rows = db.session.query(Student.id, Student.created_at).all()
    df = pd.DataFrame(
        [{"id": r.id, "created_at": r.created_at} for r in rows if r.created_at is not None]
    )
    if df.empty:
        return df
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["year"] = df["created_at"].dt.year
    df["month"] = df["created_at"].dt.month
    return df


def _ranking_alumnos_aprobados_por_profesor(df: pd.DataFrame) -> pd.DataFrame:
    """Un alumno cuenta una vez por profesor si saca >= 7 en alguna materia de ese docente.
    Incluye todos los profesores dados de alta (0 si no tienen aprobados en sus materias)."""
    db_names = [t.full_name for t in Teacher.query.order_by(Teacher.full_name).all()]
    if df.empty:
        return pd.DataFrame(
            {"teacher_name": db_names, "estudiantes_aprobados": [0] * len(db_names)}
        )

    passed = df[df["final_grade"] >= PASSING_GRADE]
    counts = passed.groupby("teacher_name")["student_name"].nunique()
    missing = sorted(set(counts.index) - set(db_names))
    ordered = db_names + missing

    return (
        pd.DataFrame({"teacher_name": ordered})
        .assign(
            estudiantes_aprobados=lambda d: d["teacher_name"]
            .map(counts)
            .fillna(0)
            .astype(int)
        )
        .sort_values("estudiantes_aprobados", ascending=False)
    )


def _analytics_payload_from_df(df: pd.DataFrame) -> dict:
    """Calcula todas las series con pandas a partir del DataFrame de notas."""
    if df.empty:
        ranking_empty = _ranking_alumnos_aprobados_por_profesor(df)
        return {
            "avg_by_subject": {"labels": [], "values": []},
            "avg_components": {
                "labels": ["Lab 1", "Lab 2", "Parcial"],
                "values": [0.0, 0.0, 0.0],
            },
            "grade_count_by_value": {"labels": [], "values": []},
            "passing_by_teacher": {
                "labels": ranking_empty["teacher_name"].tolist(),
                "values": [int(v) for v in ranking_empty["estudiantes_aprobados"].tolist()],
            },
            "grade_distribution": {"labels": [], "values": []},
        }

    avg_by_subject = (
        df.groupby("subject_name", as_index=False)["final_grade"]
        .mean()
        .sort_values("final_grade", ascending=False)
    )

    avg_components_series = df[["lab1", "lab2", "partial"]].mean()

    grade_values = list(range(10, -1, -1))
    rounded_final = df["final_grade"].round().clip(0, 10).astype(int)
    grade_counts = rounded_final.value_counts().reindex(grade_values, fill_value=0)

    passing_by_teacher = _ranking_alumnos_aprobados_por_profesor(df)

    dist_labels = ["0-3", "4-5", "6-7", "8-10"]
    categorized = pd.cut(
        df["final_grade"],
        bins=[-0.01, 3.0, 5.0, 7.0, 10.01],
        labels=dist_labels,
    )
    dist_counts = categorized.value_counts().reindex(dist_labels, fill_value=0)

    return {
        "avg_by_subject": {
            "labels": avg_by_subject["subject_name"].tolist(),
            "values": [round(v, 2) for v in avg_by_subject["final_grade"].tolist()],
        },
        "avg_components": {
            "labels": ["Lab 1", "Lab 2", "Parcial"],
            "values": [
                round(avg_components_series["lab1"], 2),
                round(avg_components_series["lab2"], 2),
                round(avg_components_series["partial"], 2),
            ],
        },
        "grade_count_by_value": {
            "labels": [str(v) for v in grade_values],
            "values": [int(v) for v in grade_counts.tolist()],
        },
        "passing_by_teacher": {
            "labels": passing_by_teacher["teacher_name"].tolist(),
            "values": [int(v) for v in passing_by_teacher["estudiantes_aprobados"].tolist()],
        },
        "grade_distribution": {
            "labels": dist_labels,
            "values": [int(v) for v in dist_counts.tolist()],
        },
    }


def _students_growth_payload(students_df: pd.DataFrame, selected_year: int | None = None) -> dict:
    month_labels = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    current_year = datetime.now().year

    if students_df.empty:
        return {
            "years": [current_year],
            "selected_year": current_year,
            "labels": month_labels,
            "values": [0] * 12,
        }

    years = sorted(students_df["year"].unique().tolist())
    year = selected_year if selected_year in years else years[-1]
    monthly = (
        students_df[students_df["year"] == year]
        .groupby("month")["id"]
        .count()
        .reindex(range(1, 13), fill_value=0)
    )
    return {
        "years": years,
        "selected_year": int(year),
        "labels": month_labels,
        "values": [int(v) for v in monthly.tolist()],
    }


@analytics_bp.route("/analytics")
@login_required
@role_required(ROLE_ADMIN)
def analytics_dashboard():
    return redirect(url_for("main.dashboard"))


@analytics_bp.route("/analytics/data")
@login_required
@role_required(ROLE_ADMIN)
def analytics_data():
    df = build_grades_dataframe()
    payload = _analytics_payload_from_df(df)
    return jsonify(payload)


@analytics_bp.route("/analytics/student-growth/data")
@login_required
@role_required(ROLE_ADMIN)
def student_growth_data():
    students_df = build_students_dataframe()
    selected_year = request.args.get("year", type=int)
    return jsonify(_students_growth_payload(students_df, selected_year))


@analytics_bp.route("/analytics/export")
@login_required
@role_required(ROLE_ADMIN)
def export_analytics():
    file_format = request.args.get("format", "png").lower()
    chart = request.args.get("chart", "subjects").lower()

    if file_format not in {"png", "pdf"}:
        return jsonify({"error": "Formato invalido. Usa png o pdf."}), 400

    df = build_grades_dataframe()

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 5))

    if chart == "students":
        if df.empty:
            return jsonify({"error": "No hay datos para generar el grafico."}), 400
        grades = list(range(10, -1, -1))
        counts = (
            df["final_grade"].round().clip(0, 10).astype(int).value_counts().reindex(grades, fill_value=0)
        )
        data = pd.DataFrame({"nota": [str(v) for v in grades], "n": counts.astype(int).to_numpy()})
        sns.barplot(data=data, x="nota", y="n", ax=ax, palette="Blues_d")
        ax.set_title("Cantidad de registros por nota final (10 a 0)")
        ax.set_xlabel("Nota final (redondeada)")
        ax.set_ylabel("Cantidad de registros")
    elif chart == "teachers":
        if df.empty:
            return jsonify({"error": "No hay datos para generar el grafico."}), 400
        ranking = _ranking_alumnos_aprobados_por_profesor(df)
        if ranking["estudiantes_aprobados"].sum() == 0:
            return jsonify({"error": "No hay aprobados para graficar por profesor."}), 400
        data = ranking[ranking["estudiantes_aprobados"] > 0]
        sns.barplot(data=data, x="estudiantes_aprobados", y="teacher_name", ax=ax, palette="Oranges_d")
        ax.set_title(
            f"Alumnos aprobados (nota final >= {PASSING_GRADE}) por profesor, en sus materias"
        )
        ax.set_xlabel("Cantidad de alumnos distintos aprobados")
        ax.set_ylabel("Profesor")
    elif chart == "distribution":
        if df.empty:
            return jsonify({"error": "No hay datos para generar el grafico."}), 400
        dist_labels = ["0-3", "4-5", "6-7", "8-10"]
        categorized = pd.cut(
            df["final_grade"],
            bins=[-0.01, 3.0, 5.0, 7.0, 10.01],
            labels=dist_labels,
        )
        vc = categorized.value_counts().reindex(dist_labels, fill_value=0)
        data = pd.DataFrame({"rango": dist_labels, "n": vc.astype(int).to_numpy()})
        sns.barplot(data=data, x="rango", y="n", ax=ax, palette="Purples_d")
        ax.set_title("Distribucion de notas finales por rango")
        ax.set_xlabel("Rango de nota final")
        ax.set_ylabel("Cantidad de registros")
    elif chart == "components":
        if df.empty:
            return jsonify({"error": "No hay datos para generar el grafico."}), 400
        means = df[["lab1", "lab2", "partial"]].mean()
        plot_df = pd.DataFrame(
            {
                "tipo": ["Lab 1", "Lab 2", "Parcial"],
                "promedio": [means["lab1"], means["lab2"], means["partial"]],
            }
        )
        sns.barplot(data=plot_df, x="tipo", y="promedio", ax=ax, palette="Set2")
        ax.set_title("Promedio global por tipo de evaluacion")
        ax.set_xlabel("Tipo de evaluacion")
        ax.set_ylabel("Promedio")
        ax.set_ylim(0, 10)
    elif chart == "student_growth":
        students_df = build_students_dataframe()
        data = _students_growth_payload(students_df, request.args.get("year", type=int))
        plot_df = pd.DataFrame({"mes": data["labels"], "n": data["values"]})
        sns.barplot(data=plot_df, x="mes", y="n", ax=ax, palette="Blues")
        ax.set_title(f"Nuevos estudiantes por mes ({data['selected_year']})")
        ax.set_xlabel("Mes")
        ax.set_ylabel("Nuevos estudiantes")
        ax.set_ylim(bottom=0)
    else:
        if df.empty:
            return jsonify({"error": "No hay datos para generar el grafico."}), 400
        data = (
            df.groupby("subject_name", as_index=False)["final_grade"]
            .mean()
            .sort_values("final_grade", ascending=False)
        )
        sns.barplot(data=data, x="subject_name", y="final_grade", ax=ax, palette="Greens_d")
        ax.set_title("Promedio final por materia")
        ax.set_xlabel("Materia")
        ax.set_ylabel("Promedio final")
        ax.tick_params(axis="x", rotation=25)

    fig.tight_layout()
    output = BytesIO()
    fig.savefig(output, format=file_format)
    plt.close(fig)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"analitica_{chart}.{file_format}",
        mimetype="application/pdf" if file_format == "pdf" else "image/png",
    )
