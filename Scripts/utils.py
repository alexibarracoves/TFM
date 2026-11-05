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
        migrarDb(conn)
        # Un escaneo que estaba en curso cuando se paró el contenedor no terminará nunca
        conn.execute("UPDATE imagenes SET estado_escaneo = 'pendiente' WHERE estado_escaneo = 'escaneando'")
        conn.commit()
    finally:
        conn.close()

def migrarDb(conn):
    # Bases de datos creadas antes de guardar el estado de los escaneos
    columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(imagenes)")}
    if "estado_escaneo" not in columnas:
        conn.execute("ALTER TABLE imagenes ADD COLUMN estado_escaneo TEXT NOT NULL DEFAULT 'pendiente'")
        conn.execute("ALTER TABLE imagenes ADD COLUMN detalle_escaneo TEXT")
        conn.execute("ALTER TABLE imagenes ADD COLUMN fecha_escaneo TEXT")
        conn.execute("UPDATE imagenes SET estado_escaneo = 'completado' WHERE numero_baja IS NOT NULL")

# Minutos que se espera antes de reintentar un escaneo que ha fallado
REINTENTO_MINUTOS = 5

def imagenesPorEscanear(imagenes):
    """Imágenes en uso ({nombre: hash}) sin escanear todavía, o cuyo último escaneo falló hace más de
    REINTENTO_MINUTOS. Devuelve el nombre con el que están registradas en la base de datos."""
    pendientes = []
    conn = get_db()
    try:
        for nombre, hash in imagenes.items():
            fila = conn.execute(f"""
                SELECT nombre, estado_escaneo, fecha_escaneo < datetime('now', '-{REINTENTO_MINUTOS} minutes')
                FROM imagenes WHERE nombre = ? OR hash = ?
            """, (nombre, hash)).fetchone()
            if not fila:
                pendientes.append(nombre)
            elif fila[1] == "pendiente" or (fila[1] == "error" and fila[2]):
                pendientes.append(fila[0])
    finally:
        conn.close()
    return list(dict.fromkeys(pendientes))

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
