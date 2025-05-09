import psycopg2
import json
import subprocess
import time
from utils import get_db, getContenedores, getImagenes, obtenerIdImagen

contador = 0

def inspect(id):
    try:
        result = subprocess.run(["podman", "inspect", id], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)[0]
    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando podman inspect para {id}: {e}")
        return None
    
def comprobarModoRoot():
    conn = None
    try:
        result = subprocess.run(["podman", "info", "--format=json"], capture_output=True, text=True, check=True)
        podman_info = json.loads(result.stdout)
        
        modo_rootless = podman_info.get("host", {}).get("security", {}).get("rootless", False)

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO podman (id, modo_root)
            VALUES (1, %s)
            ON CONFLICT (id) DO UPDATE
            SET modo_root = EXCLUDED.modo_root
        """, (not modo_rootless,))
        
        conn.commit()
        
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar podman info: {e}")
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
            cursor.execute("""
                INSERT INTO contenedores (nombre, estado, imagen_id, capacidades, puertos, interfaces)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                datosContenedor["Name"],
                datosContenedor.get("State", {}).get("Status", "desconocido"),
                obtenerIdImagen(cursor, datosContenedor["ImageName"]),
                ",".join(datosContenedor.get("EffectiveCaps", [])),
                json.dumps(datosContenedor.get("NetworkSettings", {}).get("Ports", {})),
                json.dumps(datosContenedor.get("NetworkSettings", {}).get("Networks", {}))
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