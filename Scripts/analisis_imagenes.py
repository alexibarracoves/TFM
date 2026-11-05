import os
import sys
import fcntl
import sqlite3
import json
import tempfile
import subprocess
from utils import get_db, getContenedores, getImagenes, obtenerIdImagen, imagenesPorEscanear, DB_PATH

traducciones = {
    "UNKNOWN": "Desconocida",
    "LOW": "Baja",
    "MEDIUM": "Media",
    "HIGH": "Alta",
    "CRITICAL": "Crítica",
    "affected": "Afectado",
    "fixed": "Corregido",
    "will_not_fix": "No se corregirá",
    "fix_deferred": "Corrección aplazada",
    "end_of_life": "Sin soporte",
    "under_investigation": "En investigación",
    "not_affected": "No afectado"
}

def actualizarImagenes(images):
    conn = get_db()
    try:
        cursor = conn.cursor()
        for nombre, hash in images.items():
            cursor.execute("SELECT id FROM imagenes WHERE nombre = ? OR hash = ?", (nombre, hash))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO imagenes (nombre, hash) VALUES (?, ?)", (nombre, hash))

        conn.commit()
    except sqlite3.Error as e:
        print(f"Error de base de datos al actualizar imágenes: {e}")
    finally:
        conn.close()

def marcarEstado(nombre, estado, detalle=None):
    conn = get_db()
    try:
        conn.execute("""
            UPDATE imagenes SET estado_escaneo = ?, detalle_escaneo = ?, fecha_escaneo = datetime('now')
            WHERE nombre = ?
        """, (estado, detalle, nombre))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error de base de datos al actualizar el estado del escaneo de {nombre}: {e}")
    finally:
        conn.close()

def ejecutarTrivy(nombre):
    with tempfile.NamedTemporaryFile() as tmpfile:
        proceso = subprocess.run([
            "trivy", "image", "--scanners", "vuln", "--skip-version-check", "--quiet",
            "--format", "json", "-o", tmpfile.name, nombre
        ], capture_output=True, text=True)
        if proceso.returncode != 0:
            lineas = [l for l in proceso.stderr.splitlines() if l.strip()]
            raise RuntimeError(lineas[-1] if lineas else f"Trivy terminó con código {proceso.returncode}")
        tmpfile.seek(0)
        return json.load(tmpfile)

def evaluarSoporte(resultado):
    # Si Trivy reconoce el sistema operativo pero no lo soporta, no devuelve resultado de paquetes del sistema
    sistema = resultado.get("Metadata", {}).get("OS")
    if not sistema:
        return None
    if any(r.get("Class") == "os-pkgs" for r in resultado.get("Results") or []):
        return None
    return f"Trivy no analiza los paquetes de {sistema.get('Family', '?')} {sistema.get('Name', '')}".strip()

def insertarVulnerabilidades(nombre, vulnerabilidades, estado, detalle):
    conn = get_db()
    try:
        cursor = conn.cursor()
        idImagen = obtenerIdImagen(cursor, nombre)
        if not idImagen:
            print(f"No se encontró la imagen {nombre} en la base de datos.")
            return

        cursor.execute("DELETE FROM vulnerabilidades WHERE imagen_id = ?", (idImagen,))

        conteo_severidades = {
            "Desconocida": 0,
            "Baja": 0,
            "Media": 0,
            "Alta": 0,
            "Crítica": 0
        }

        for vuln in vulnerabilidades:
            for componentes in vuln.get("Vulnerabilities", []):
                severidad = traducciones.get(componentes["Severity"], "Desconocida")
                conteo_severidades[severidad] += 1
                cursor.execute("""
                    INSERT INTO vulnerabilidades
                    (imagen_id, vulnerabilidad, libreria, severidad, estado, version, informacion, enlace)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    idImagen,
                    componentes["VulnerabilityID"],
                    componentes["PkgName"],
                    severidad,
                    traducciones.get(componentes.get("Status"), componentes.get("Status")),
                    componentes.get("InstalledVersion", ""),
                    componentes.get("Title", ""),
                    componentes.get("PrimaryURL", "")
                ))

        cursor.execute("""
            UPDATE imagenes SET numero_desconocida = ?, numero_baja = ?, numero_media = ?, numero_alta = ?, numero_critica = ?,
                estado_escaneo = ?, detalle_escaneo = ?, fecha_escaneo = datetime('now')
            WHERE id = ?
        """, (
            conteo_severidades["Desconocida"], conteo_severidades["Baja"], conteo_severidades["Media"], conteo_severidades["Alta"], conteo_severidades["Crítica"],
            estado, detalle, idImagen
        ))

        conn.commit()
    except sqlite3.Error as e:
        print(f"Error de base de datos al almacenar vulnerabilidades: {e}")
    finally:
        conn.close()

def escanear(imagen):
    print(f"Escaneando {imagen} con Trivy...")
    marcarEstado(imagen, "escaneando")
    try:
        resultado = ejecutarTrivy(imagen)
    except (RuntimeError, OSError, json.JSONDecodeError) as e:
        print(f"Error ejecutando Trivy en {imagen}: {e}")
        marcarEstado(imagen, "error", str(e)[:500])
        return
    detalle = evaluarSoporte(resultado)
    insertarVulnerabilidades(imagen, resultado.get("Results") or [], "no_soportado" if detalle else "completado", detalle)

def main(todas):
    # Evita que dos escaneos se solapen (el periódico y el de imágenes nuevas, o uno lanzado a mano)
    cerrojo = open(os.path.join(os.path.dirname(DB_PATH), "escaneo.lock"), "w")
    try:
        fcntl.flock(cerrojo, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Ya hay un escaneo en curso.")
        return

    print("Iniciando escaneo de imágenes...")
    contenedores = getContenedores()
    if not contenedores:
        print("No hay contenedores en ejecución.")
    else:
        imagenes = getImagenes(contenedores)
        actualizarImagenes(imagenes)
        nombres = list(imagenes.keys()) if todas else imagenesPorEscanear(imagenes)
        for imagen in nombres:
            escanear(imagen)
    print("Escaneo finalizado.")

if __name__ == "__main__":
    main(todas="--todas" in sys.argv)
