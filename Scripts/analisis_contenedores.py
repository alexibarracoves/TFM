import psycopg2
import json
import subprocess
import time
import docker
import motor
from utils import get_db, getContenedores, getImagenes, obtenerIdImagen

contador = 0

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
            VALUES (1, %s, %s)
            ON CONFLICT (id) DO UPDATE
            SET nombre = EXCLUDED.nombre, modo_root = EXCLUDED.modo_root
        """, (motor.NOMBRE, modo_root))

        conn.commit()

    except docker.errors.DockerException as e:
        print(f"Error al consultar la información del motor: {e}")
    except psycopg2.Error as e:
        print(f"Error de base de datos al actualizar el modo root: {e}")
    finally:
        if conn:
            conn.close()

def comprobarImagenes(contenedores):
    global contador
    conn = get_db()
    try:
        cursor = conn.cursor()
        nueva = False
        for nombre, hash in getImagenes(contenedores).items():
            cursor.execute("SELECT id FROM imagenes WHERE nombre = %s OR hash = %s", (nombre, hash))
            if not cursor.fetchone():
                nueva = True
                break

        if nueva:
            print("Imagenes nuevas detectadas, ejecutando análisis...")
            subprocess.Popen(["python3", "/app/Scripts/analisis_imagenes.py"])
            contador = 0
    except psycopg2.Error as e:
        print(f"Error de base de datos al actualizar imágenes: {e}")
    finally:
        conn.close()

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
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                datosContenedor["nombre"],
                datosContenedor["estado"],
                obtenerIdImagen(cursor, contenedor["Image"]),
                ",".join(datosContenedor["capacidades"]),
                json.dumps(datosContenedor["puertos"]),
                json.dumps(datosContenedor["redes"])
            ))
        conn.commit()
    except psycopg2.Error as e:
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
        if contador == 120:
            contador = 0
            subprocess.Popen(["python3", "/app/Scripts/analisis_imagenes.py"])
        time.sleep(5)

if __name__ == "__main__":
    analizarContenedores()