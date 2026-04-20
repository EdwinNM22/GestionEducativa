# Documentacion del proyecto

Proyecto Flask con frontend integrado en Jinja, autenticacion y persistencia en MySQL.

## Librerias instaladas y uso

- `Flask`: framework principal para la aplicacion web.
- `Flask-SQLAlchemy`: ORM para conectar y trabajar con la base de datos.
- `Flask-Migrate`: soporte de migraciones con Alembic.
- `PyMySQL`: driver de conexion para MySQL.
- `pandas`: procesamiento de datos tabulares.
- `seaborn`: visualizacion estadistica.
- `matplotlib`: motor de render para exportar graficos a PNG/PDF.
- `faker`: generacion de datos de prueba.

## Estructura base

- `app.py`: punto de entrada de la aplicacion.
- `app/__init__.py`: configuracion general, DB, migraciones y registro de blueprints.
- `app/models.py`: modelos de base de datos (`User`).
- `app/auth.py`: rutas de login, registro y logout.
- `app/routes.py`: rutas principales (`/` y `/dashboard`).
- `app/education.py`: CRUD de estudiantes, profesores, materias y notas.
- `app/analytics.py`: endpoints de analitica, datos en tiempo real y exportacion de graficos.
- `app/templates/`: vistas Jinja (`login`, `register`, `dashboard`, `base`).
- `app/static/`: CSS y JS del frontend.
- `.env.example`: variables de entorno de ejemplo.

## Variables de entorno

Crear un archivo `.env` basado en `.env.example`:

- `SECRET_KEY`: clave para sesiones.
- `DATABASE_URL`: cadena de conexion, ejemplo:
  `mysql+pymysql://root:tu_password@localhost:3306/gestion-educativa-db`

## Flujo de autenticacion

- Registro en `/register`.
- Login en `/login`.
- Si el login es correcto, redirige a `/dashboard`.
- Dashboard protegido: si no hay sesion, redirige a login.

## Analitica en tiempo real y exportacion

- Vista de analitica: `/analytics`.
- Fuente dinamica para Chart.js: `/analytics/data` (actualizacion cada 5 segundos).
- Exportacion de graficos generados con seaborn:
  - `/analytics/export?chart=subjects&format=png`
  - `/analytics/export?chart=subjects&format=pdf`
  - `/analytics/export?chart=students&format=png`
  - `/analytics/export?chart=students&format=pdf`
