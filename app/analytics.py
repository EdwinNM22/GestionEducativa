from io import BytesIO

import matplotlib
import pandas as pd
import seaborn as sns
from flask import Blueprint, jsonify, render_template, request, send_file

from .auth import login_required
from .extensions import db
from .models import Enrollment, Student, Subject

matplotlib.use("Agg")
import matplotlib.pyplot as plt

analytics_bp = Blueprint("analytics", __name__)


def build_grades_dataframe():
    rows = (
        db.session.query(
            Enrollment.id,
            Enrollment.lab1,
            Enrollment.lab2,
            Enrollment.partial,
            Student.full_name.label("student_name"),
            Subject.name.label("subject_name"),
        )
        .join(Student, Student.id == Enrollment.student_id)
        .join(Subject, Subject.id == Enrollment.subject_id)
        .all()
    )

    data = [
        {
            "id": row.id,
            "student_name": row.student_name,
            "subject_name": row.subject_name,
            "lab1": row.lab1,
            "lab2": row.lab2,
            "partial": row.partial,
            "final_grade": round((row.lab1 * 0.25) + (row.lab2 * 0.25) + (row.partial * 0.50), 2),
        }
        for row in rows
    ]
    return pd.DataFrame(data)


@analytics_bp.route("/analytics")
@login_required
def analytics_dashboard():
    return render_template("analytics.html")


@analytics_bp.route("/analytics/data")
@login_required
def analytics_data():
    df = build_grades_dataframe()
    if df.empty:
        return jsonify(
            {
                "avg_by_subject": {"labels": [], "values": []},
                "avg_components": {"labels": ["Lab 1", "Lab 2", "Parcial"], "values": [0, 0, 0]},
                "top_students": {"labels": [], "values": []},
            }
        )

    avg_by_subject = (
        df.groupby("subject_name", as_index=False)["final_grade"]
        .mean()
        .sort_values("final_grade", ascending=False)
    )
    avg_components = [df["lab1"].mean(), df["lab2"].mean(), df["partial"].mean()]
    top_students = (
        df.groupby("student_name", as_index=False)["final_grade"]
        .mean()
        .sort_values("final_grade", ascending=False)
        .head(5)
    )

    return jsonify(
        {
            "avg_by_subject": {
                "labels": avg_by_subject["subject_name"].tolist(),
                "values": [round(v, 2) for v in avg_by_subject["final_grade"].tolist()],
            },
            "avg_components": {
                "labels": ["Lab 1", "Lab 2", "Parcial"],
                "values": [round(v, 2) for v in avg_components],
            },
            "top_students": {
                "labels": top_students["student_name"].tolist(),
                "values": [round(v, 2) for v in top_students["final_grade"].tolist()],
            },
        }
    )


@analytics_bp.route("/analytics/export")
@login_required
def export_analytics():
    file_format = request.args.get("format", "png").lower()
    chart = request.args.get("chart", "subjects").lower()

    if file_format not in {"png", "pdf"}:
        return jsonify({"error": "Formato invalido. Usa png o pdf."}), 400

    df = build_grades_dataframe()
    if df.empty:
        return jsonify({"error": "No hay datos para generar el grafico."}), 400

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 5))

    if chart == "students":
        data = (
            df.groupby("student_name", as_index=False)["final_grade"]
            .mean()
            .sort_values("final_grade", ascending=False)
            .head(10)
        )
        sns.barplot(data=data, x="final_grade", y="student_name", ax=ax, palette="Blues_d")
        ax.set_title("Top estudiantes por promedio final")
        ax.set_xlabel("Promedio final")
        ax.set_ylabel("Estudiante")
    else:
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
