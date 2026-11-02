import os
import sqlite3
import docker
import motor

DB_PATH = os.environ.get("DB_PATH", "/app/data/analizador.db")
ESQUEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_init.sql")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def inicializarDb():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    try:
        # WAL permite que la API lea mientras el recolector escribe
        conn.execute("PRAGMA journal_mode = WAL")
        with open(ESQUEMA, encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()

def getContenedores():
    try:
        return motor.listarContenedores()
    except docker.errors.DockerException as e:
        print(f"Error listando los contenedores: {e}")
        return []

def getImagenes(contenedores):
    imagenes = {}
    for contenedor in contenedores:
        imagen = contenedor["Image"]
        hash = contenedor["ImageID"]
        if imagen not in imagenes:
            imagenes[imagen] = hash
    return imagenes

def obtenerIdImagen(cursor, nombre):
    cursor.execute("SELECT id FROM imagenes WHERE nombre = ?", (nombre,))
    idImagen = cursor.fetchone()
    if not idImagen:
        return None
    else:
        return idImagen[0]
