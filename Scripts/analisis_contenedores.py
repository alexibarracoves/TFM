import sqlite3
import json
import subprocess
import time
import docker
import motor
from utils import get_db, getContenedores, getImagenes, obtenerIdImagen, imagenesPorEscanear

contador = 0
escaneo = None

def lanzarEscaneo(*argumentos):
    global escaneo
    if escaneo and escaneo.poll() is None:
        return False
    escaneo = subprocess.Popen(["python3", "/app/Scripts/analisis_imagenes.py", *argumentos])
    return True

def inspect(id):
    try:
        return motor.inspeccionar(id)
    except docker.errors.DockerException as e:
        print(f"Error inspeccionando el contenedor {id}: {e}")
        return None

def comprobarModoRoot():
    conn = None
    try:
        modo_root = motor.modoRoot()

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO motor (id, nombre, modo_root)
            VALUES (1, ?, ?)
            ON CONFLICT (id) DO UPDATE
            SET nombre = EXCLUDED.nombre, modo_root = EXCLUDED.modo_root
        """, (motor.NOMBRE, modo_root))

        conn.commit()

    except docker.errors.DockerException as e:
        print(f"Error al consultar la información del motor: {e}")
    except sqlite3.Error as e:
        print(f"Error de base de datos al actualizar el modo root: {e}")
    finally:
        if conn:
            conn.close()

def comprobarImagenes(contenedores):
    global contador
    try:
        pendientes = imagenesPorEscanear(getImagenes(contenedores))
        if pendientes and lanzarEscaneo():
            print(f"Imágenes pendientes de escanear: {', '.join(pendientes)}")
            contador = 0
    except sqlite3.Error as e:
        print(f"Error de base de datos al comprobar imágenes: {e}")

def insertarInfo(contenedores):
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM contenedores")
        for contenedor in contenedores:
            datosContenedor = inspect(contenedor["Id"])
            if not datosContenedor:
                continue
            cursor.execute("""
                INSERT INTO contenedores (nombre, estado, imagen_id, capacidades, puertos, interfaces)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datosContenedor["nombre"],
                datosContenedor["estado"],
                obtenerIdImagen(cursor, contenedor["Image"]),
                ",".join(datosContenedor["capacidades"]),
                json.dumps(datosContenedor["puertos"]),
                json.dumps(datosContenedor["redes"])
            ))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error de base de datos: {e}")
    finally:
        if conn:
            conn.close()

def analizarContenedores():
    global contador
    while True:
        contador += 1
        comprobarModoRoot()
        contenedores = getContenedores()
        if contenedores:
            comprobarImagenes(contenedores)
            insertarInfo(contenedores)
        # Reescaneo completo cada ~10 minutos para detectar vulnerabilidades nuevas en imágenes ya conocidas
        if contador >= 120 and lanzarEscaneo("--todas"):
            contador = 0
        time.sleep(5)

if __name__ == "__main__":
    analizarContenedores()