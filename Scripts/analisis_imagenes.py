import psycopg2
import json
import tempfile
import subprocess
from utils import get_db, getContenedores, getImagenes, obtenerIdImagen

traducciones = {
    "UNKNOWN": "Desconocida",
    "LOW": "Baja",
    "MEDIUM": "Media",
    "HIGH": "Alta",
    "CRITICAL": "Crítica",
    "affected": "Afectado",
    "fixed": "Corregido"
}

def actualizarImagenes(images):
    conn = get_db()
    try:
        cursor = conn.cursor()
        for nombre, hash in images.items():
            cursor.execute("SELECT id FROM imagenes WHERE nombre = %s OR hash = %s", (nombre, hash))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO imagenes (nombre, hash) VALUES (%s, %s)", (nombre, hash))

        conn.commit()
    except psycopg2.Error as e:
        print(f"Error de base de datos al actualizar imágenes: {e}")
    finally:
        conn.close()

def ejecutarTrivy(nombre):
    try:
        with tempfile.NamedTemporaryFile() as tmpfile:
            subprocess.run(["trivy", "image", "--format", "json", "-o", tmpfile.name, nombre], check=True)
            tmpfile.seek(0)
            resultado_json = json.load(tmpfile)
        return resultado_json

    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando Trivy en {nombre}: {e}")
        return None

def insertarVulnerabilidades(nombre, vulnerabilidades):
    conn = get_db()
    try:
        cursor = conn.cursor()
        idImagen = obtenerIdImagen(cursor, nombre)
        if not idImagen:
            print(f"No se encontró la imagen {nombre} en la base de datos.")
            return

        cursor.execute("DELETE FROM vulnerabilidades WHERE imagen_id = %s", (idImagen,))

        conteo_severidades = {
            "Desconocida": 0,
            "Baja": 0,
            "Media": 0,
            "Alta": 0,
            "Crítica": 0
        }

        for vuln in vulnerabilidades:
            for componentes in vuln.get("Vulnerabilities", []):
                severidad = traducciones.get(componentes["Severity"], "UNKNOWN")
                conteo_severidades[severidad] += 1
                cursor.execute("""
                    INSERT INTO vulnerabilidades 
                    (imagen_id, vulnerabilidad, libreria, severidad, estado, version, informacion, enlace) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    idImagen,
                    componentes["VulnerabilityID"],
                    componentes["PkgName"],
                    severidad,
                    traducciones.get(componentes["Status"]),
                    componentes.get("InstalledVersion", ""),
                    componentes.get("Title", ""),
                    componentes.get("PrimaryURL", "")
                ))

        cursor.execute("""
            UPDATE imagenes SET numero_desconocida = %s, numero_baja = %s, numero_media = %s, numero_alta = %s, numero_critica = %s WHERE id = %s
        """, (
            conteo_severidades["Desconocida"], conteo_severidades["Baja"], conteo_severidades["Media"], conteo_severidades["Alta"], conteo_severidades["Crítica"], idImagen
        ))
        
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error de base de datos al almacenar vulnerabilidades: {e}")
    finally:
        conn.close()

def main():
        print("Iniciando escaneo de imágenes...")
        contenedores = getContenedores()
        if not contenedores:
            print("No hay contenedores en ejecución.")
        else:
            imagenes = getImagenes(contenedores)
            actualizarImagenes(imagenes)
            for imagen in imagenes.keys():
                print(f"Escaneando {imagen} con Trivy...")
                trivy_result = ejecutarTrivy(imagen)
                if trivy_result and "Results" in trivy_result:
                    insertarVulnerabilidades(imagen, trivy_result["Results"])
        print("Escaneo finalizado.")

if __name__ == "__main__":
        main()