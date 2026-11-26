from datetime import datetime
import os
import sqlite3
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
DB_NAME = "santuario.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def get_db():
    """Retorna (conexion, es_postgres)."""
    if DATABASE_URL:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn, True

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn, False


def ph(es_postgres):
    """Devuelve el marcador de parámetro adecuado (%s para Postgres, ? para SQLite)."""
    return "%s" if es_postgres else "?"


def init_db():
    """Crea las tablas si aún no existen, tanto en SQLite como en PostgreSQL."""
    conn, es_postgres = get_db()
    cursor = conn.cursor()

    if es_postgres:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                apodo TEXT UNIQUE NOT NULL,
                creado_en TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dedicatorias (
                id SERIAL PRIMARY KEY,
                autor TEXT NOT NULL,
                destinatario TEXT NOT NULL,
                mensaje TEXT NOT NULL,
                estado_animo TEXT NOT NULL,
                fecha TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS respuestas_juego (
                id SERIAL PRIMARY KEY,
                jugador TEXT NOT NULL,
                pregunta TEXT NOT NULL,
                respuesta TEXT NOT NULL,
                fecha TEXT NOT NULL
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                apodo TEXT UNIQUE NOT NULL,
                creado_en TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dedicatorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                autor TEXT NOT NULL,
                destinatario TEXT NOT NULL,
                mensaje TEXT NOT NULL,
                estado_animo TEXT NOT NULL,
                fecha TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS respuestas_juego (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jugador TEXT NOT NULL,
                pregunta TEXT NOT NULL,
                respuesta TEXT NOT NULL,
                fecha TEXT NOT NULL
            )
        """)

    conn.commit()
    conn.close()


def registrar_apodo_si_no_existe(cursor, apodo, es_postgres):
    apodo_limpio = (apodo or "").strip()
    if not apodo_limpio:
        return
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    p = ph(es_postgres)
    if es_postgres:
        cursor.execute(
            f"INSERT INTO usuarios (apodo, creado_en) VALUES ({p}, {p}) ON CONFLICT (apodo) DO NOTHING",
            (apodo_limpio, fecha),
        )
    else:
        cursor.execute(
            f"INSERT OR IGNORE INTO usuarios (apodo, creado_en) VALUES ({p}, {p})",
            (apodo_limpio, fecha),
        )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/usuarios", methods=["GET"])
def listar_usuarios():
    conn, _ = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios ORDER BY id ASC")
    filas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(filas)


@app.route("/api/usuarios", methods=["POST"])
def crear_o_seleccionar_usuario():
    datos = request.json or {}
    apodo = datos.get("apodo", "").strip()
    if not apodo:
        return jsonify({"error": "Escribe un apodo o nombre"}), 400

    conn, es_postgres = get_db()
    cursor = conn.cursor()
    registrar_apodo_si_no_existe(cursor, apodo, es_postgres)
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "apodo": apodo}), 201


@app.route("/api/perfiles", methods=["GET"])
def obtener_perfiles():
    conn, _ = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT apodo FROM usuarios ORDER BY id ASC")
    apodos_registrados = [row["apodo"] for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM respuestas_juego ORDER BY id DESC")
    respuestas = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM dedicatorias ORDER BY id DESC")
    dedicatorias = [dict(d) for d in cursor.fetchall()]
    conn.close()

    todos_los_apodos = list(apodos_registrados)
    for r in respuestas:
        if r["jugador"] not in todos_los_apodos:
            todos_los_apodos.append(r["jugador"])
    for d in dedicatorias:
        if d["autor"] not in todos_los_apodos:
            todos_los_apodos.append(d["autor"])

    perfiles = []
    for apodo in todos_los_apodos:
        perfiles.append({
            "apodo": apodo,
            "respuestas": [r for r in respuestas if r["jugador"] == apodo],
            "dedicatorias": [d for d in dedicatorias if d["autor"] == apodo],
        })

    return jsonify(perfiles)


@app.route("/api/dedicatorias", methods=["GET"])
def obtener_dedicatorias():
    conn, _ = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dedicatorias ORDER BY id DESC")
    filas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(filas)


@app.route("/api/dedicatorias", methods=["POST"])
def guardar_dedicatoria():
    datos = request.json or {}
    autor = datos.get("autor", "").strip()
    destinatario = datos.get("destinatario", "Mi Eternidad").strip()
    mensaje = datos.get("mensaje", "").strip()
    estado_animo = datos.get("estado_animo", "🥀 Devoción Eterna")
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    if not autor:
        return jsonify({"error": "Debes indicar tu apodo o nombre"}), 400
    if not mensaje:
        return jsonify({"error": "El mensaje no puede estar vacío"}), 400

    conn, es_postgres = get_db()
    cursor = conn.cursor()
    p = ph(es_postgres)
    registrar_apodo_si_no_existe(cursor, autor, es_postgres)
    cursor.execute(
        f"INSERT INTO dedicatorias (autor, destinatario, mensaje, estado_animo, fecha) VALUES ({p}, {p}, {p}, {p}, {p})",
        (autor, destinatario, mensaje, estado_animo, fecha),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "guardado"}), 201


@app.route("/api/respuestas", methods=["GET"])
def obtener_respuestas():
    conn, _ = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM respuestas_juego ORDER BY id DESC")
    filas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(filas)


@app.route("/api/respuestas", methods=["POST"])
def guardar_respuesta():
    datos = request.json or {}
    jugador = datos.get("jugador", "").strip()
    pregunta = datos.get("pregunta", "").strip()
    respuesta = datos.get("respuesta", "").strip()
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    if not jugador:
        return jsonify({"error": "Debes indicar tu apodo o nombre"}), 400
    if not respuesta:
        return jsonify({"error": "Debes escribir una respuesta"}), 400

    conn, es_postgres = get_db()
    cursor = conn.cursor()
    p = ph(es_postgres)
    registrar_apodo_si_no_existe(cursor, jugador, es_postgres)
    cursor.execute(
        f"INSERT INTO respuestas_juego (jugador, pregunta, respuesta, fecha) VALUES ({p}, {p}, {p}, {p})",
        (jugador, pregunta, respuesta, fecha),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "guardado"}), 201


try:
    init_db()
except Exception as exc:
    print(f"Aviso al inicializar BD: {exc}")

if __name__ == "__main__":
    print("Santuario activo en: http://127.0.0.1:5000")
    app.run(debug=True)