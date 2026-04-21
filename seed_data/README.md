# Datos de prueba (seed) para MySQL

## Requisitos

- Python 3.10+
- `pip install faker werkzeug` (o usar el `requirements.txt` del proyecto raíz)

## Generar el SQL

```bash
cd seed_data
python generate_seed.py
```

Salida: `output/seed_demo.sql` (por defecto ~20 000 filas académicas: estudiantes + notas + materias + profesores).

Opciones útiles:

```bash
python generate_seed.py --students 5000 --teachers 50 --subjects 60 --target-rows 25000
python generate_seed.py --admin-password miClaveSegura --seed 7
python generate_seed.py --output output/mi_seed.sql
```

- **`--target-rows`**: suma objetivo de filas en `teachers + subjects + students + enrollments` (no incluye la tabla `users`).
- **`--target-rows` − teachers − subjects − students** = cantidad de registros en `enrollments` (notas). No puede superar `students × subjects` (pares únicos alumno–materia).

## Importar en MySQL

**Ojo:** el script hace `TRUNCATE` de `enrollments`, `users`, `subjects`, `students` y `teachers`. Haz copia de seguridad antes.

Tras aplicar migraciones Alembic en una base vacía o de desarrollo:

```bash
mysql -u root -p nombre_base < seed_data/output/seed_demo.sql
```

O desde el cliente MySQL: `SOURCE ruta/al/seed_demo.sql;`

## Cuentas generadas

| Usuario   | Rol     | Contraseña por defecto |
|-----------|---------|-------------------------|
| `admin`   | admin   | `demo123` (`--admin-password`) |
| `profesor1` … `profesor45` | teacher | la misma |
| Email admin: `admin@demo.local` | | |
| Profesores: `profesor.seed.N@demo.local` | | |

Los **alumnos** solo existen en `students` (sin fila en `users`), para no multiplicar cuentas de login. Puedes crear usuarios alumno desde la app si lo necesitas.

## Esquema

Los `INSERT` respetan el modelo actual: claves foráneas, `uq_student_subject` en `enrollments`, códigos `SUB00001`… únicos en `subjects`, notas 0–10 con distribución realista.
