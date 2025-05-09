import psycopg2
import subprocess
import json

DB_CONFIG = {
    "dbname": "contenedores",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

def getContenedores():
    try:
        resultado = subprocess.run(["podman", "ps", "--format", "json"], capture_output=True, text=True, check=True)
        return json.loads(resultado.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando podman ps: {e}")
        return []
    
def getImagenes(contenedores):
    imagenes = {}
    for contenedor in contenedores:
        imagen = contenedor["Image"]
        hash = contenedor["ImageID"]
        if "localhost" in imagen:
            continue
        if imagen not in imagenes:
            imagenes[imagen] = hash
    return imagenes

def obtenerIdImagen(cursor, nombre):
    cursor.execute("SELECT id FROM imagenes WHERE nombre = %s", (nombre,))
    idImagen = cursor.fetchone()
    if not idImagen:
        return None
    else:
        return idImagen[0]