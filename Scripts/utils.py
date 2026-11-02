import psycopg2
import docker
import motor

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
    cursor.execute("SELECT id FROM imagenes WHERE nombre = %s", (nombre,))
    idImagen = cursor.fetchone()
    if not idImagen:
        return None
    else:
        return idImagen[0]
