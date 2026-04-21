"""Utilidades compartidas para validar notas (0-10)."""

PASSING_GRADE = 7.0


def is_passing(final_grade: float) -> bool:
    return final_grade >= PASSING_GRADE


def parse_grade(value):
    try:
        grade = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= grade <= 10:
        return grade
    return None
