import os
import re
import sys
import json
import math
import hmac
import sqlite3
import hashlib
import mimetypes
import threading
import subprocess
from http import HTTPStatus
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs, unquote, urlencode

PUERTO = int(os.environ.get("PUERTO", "3000"))
DB_PATH = os.environ.get("DB_PATH", "/app/data/analizador.db")
TOKEN = os.environ.get("ANALIZADOR_TOKEN", "")
COOKIE = "analizador_token"

DIRECTORIO = os.path.dirname(os.path.abspath(__file__))
PUBLICO = os.path.join(DIRECTORIO, "public")
SCRIPT_LOGS = os.path.join(DIRECTORIO, "..", "Scripts", "analisis_logs.py")

# Nombres válidos de contenedor en Docker y Podman
NOMBRE_CONTENEDOR = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,254}$")
NUM_LINEAS_LOGS = 10000
MAX_ANALISIS_LOGS = 2
TIEMPO_MAXIMO_ANALISIS = 120
analisis_en_curso = threading.BoundedSemaphore(MAX_ANALISIS_LOGS)

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])

CABECERAS_SEGURIDAD = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}

PAGINA_TOKEN = (
    '<!doctype html><meta charset="utf-8"><title>Acceso restringido</title>'
    "<p>Este analizador requiere un token. Abre la dirección con <code>?token=&lt;tu token&gt;</code>.</p>"
)

def consulta(sql, parametros=()):
    # La API solo lee: el recolector de Python es el único que escribe
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(fila) for fila in conn.execute(sql, parametros)]
    finally:
        conn.close()

def paginacion(query):
    def entero(clave, defecto):
        try:
            return int(query.get(clave, [defecto])[0])
        except ValueError:
            return defecto
    page = max(entero("page", 0), 0)
    size = min(max(entero("size", 5), 1), 100)
    return size, page * size

def tokenValido(valor):
    if not valor:
        return False
    # Se comparan los hashes para que el tiempo no dependa de la longitud del token
    a = hashlib.sha256(valor.encode()).digest()
    b = hashlib.sha256(TOKEN.encode()).digest()
    return hmac.compare_digest(a, b)

class Error(Exception):
    def __init__(self, estado, cuerpo):
        self.estado = estado
        self.cuerpo = cuerpo

# ---- Rutas de la API ----

def rutaContenedores(query):
    size, offset = paginacion(query)
    filas = consulta("""
        SELECT c.id, c.nombre, c.estado, i.id AS imagen_id, i.nombre AS imagen_nombre, c.capacidades, c.puertos, c.interfaces
        FROM contenedores c
        LEFT JOIN imagenes i ON c.imagen_id = i.id
        ORDER BY c.id
        LIMIT ? OFFSET ?
    """, (size, offset))
    total = consulta("SELECT COUNT(*) AS total FROM contenedores")[0]["total"]
    motor = (consulta("SELECT nombre, modo_root FROM motor LIMIT 1") or [None])[0]
    for fila in filas:
        fila["puertos"] = json.loads(fila["puertos"])
        fila["interfaces"] = json.loads(fila["interfaces"])
    return {
        "data": filas,
        "totalPages": math.ceil(total / size),
        "totalItems": total,
        "motor": motor["nombre"] if motor else None,
        "modo": ("root" if motor["modo_root"] else "rootless") if motor else None,
    }

def rutaVulnerabilidades(query, id_imagen):
    size, offset = paginacion(query)
    filas = consulta("""
        SELECT vulnerabilidad, libreria, severidad, estado, version, informacion, enlace
        FROM vulnerabilidades
        WHERE imagen_id = ?
        ORDER BY id
        LIMIT ? OFFSET ?
    """, (id_imagen, size, offset))
    total = consulta("SELECT COUNT(*) AS total FROM vulnerabilidades WHERE imagen_id = ?", (id_imagen,))[0]["total"]
    return {"data": filas, "totalPages": math.ceil(total / size), "totalItems": total}

def rutaImagen(query, id_imagen):
    filas = consulta("""
        SELECT id, nombre, hash, numero_desconocida, numero_baja, numero_media, numero_alta, numero_critica,
               estado_escaneo, detalle_escaneo, fecha_escaneo
        FROM imagenes
        WHERE id = ?
    """, (id_imagen,))
    if not filas:
        raise Error(HTTPStatus.NOT_FOUND, {"error": "Imagen no encontrada"})
    return filas[0]

def rutaResumenLogs(query, nombre):
    # Solo se analizan contenedores que el recolector tiene registrados
    if not NOMBRE_CONTENEDOR.match(nombre) or not consulta("SELECT 1 FROM contenedores WHERE nombre = ?", (nombre,)):
        raise Error(HTTPStatus.NOT_FOUND, {"resumen": "Contenedor no encontrado."})
    if not analisis_en_curso.acquire(blocking=False):
        raise Error(HTTPStatus.TOO_MANY_REQUESTS, {"resumen": "Hay demasiados análisis en curso. Inténtalo de nuevo en unos segundos."})
    try:
        # En un proceso aparte para no cargar scikit-learn en la API y poder cortar los análisis que se alarguen
        proceso = subprocess.run(
            [sys.executable, SCRIPT_LOGS, nombre, str(NUM_LINEAS_LOGS)],
            capture_output=True, text=True, timeout=TIEMPO_MAXIMO_ANALISIS
        )
    except subprocess.TimeoutExpired:
        print(f"El análisis de logs de {nombre} superó {TIEMPO_MAXIMO_ANALISIS} s", flush=True)
        raise Error(HTTPStatus.INTERNAL_SERVER_ERROR, {"resumen": "Error al analizar los logs."})
    finally:
        analisis_en_curso.release()
    if proceso.returncode != 0:
        print(f"Error ejecutando el script de análisis: {proceso.stderr.strip()}", flush=True)
        raise Error(HTTPStatus.INTERNAL_SERVER_ERROR, {"resumen": "Error al analizar los logs."})
    return {"resumen": proceso.stdout.strip()}

def rutaSalud(query):
    try:
        consulta("SELECT 1")
    except sqlite3.Error:
        raise Error(HTTPStatus.SERVICE_UNAVAILABLE, {"estado": "error"})
    return {"estado": "ok"}

RUTAS = [
    (re.compile(r"^/contenedores$"), rutaContenedores),
    (re.compile(r"^/vulnerabilidades/([^/]+)$"), rutaVulnerabilidades),
    (re.compile(r"^/imagenes/([^/]+)$"), rutaImagen),
    (re.compile(r"^/contenedores/([^/]+)/logs/resumen$"), rutaResumenLogs),
    (re.compile(r"^/salud$"), rutaSalud),
]

class Manejador(BaseHTTPRequestHandler):
    server_version = "analizador"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def log_message(self, formato, *args):
        # El panel consulta la API cada pocos segundos: no se registra cada petición
        pass

    def do_HEAD(self):
        self.atender(cuerpo=False)

    def do_GET(self):
        self.atender(cuerpo=True)

    def atender(self, cuerpo):
        self.enviar_cuerpo = cuerpo
        url = urlsplit(self.path)
        ruta = unquote(url.path)
        query = parse_qs(url.query)

        if not self.autenticar(url, ruta, query):
            return

        # Se enruta sobre la ruta sin decodificar para que un %2F en un parámetro no cree segmentos nuevos
        for patron, funcion in RUTAS:
            m = patron.match(url.path)
            if m:
                try:
                    self.responderJson(HTTPStatus.OK, funcion(query, *map(unquote, m.groups())))
                except Error as e:
                    self.responderJson(e.estado, e.cuerpo)
                except Exception as e:
                    print(f"Error en {ruta}: {e!r}", flush=True)
                    self.responderJson(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Error interno del servidor"})
                return

        self.servirEstatico(ruta)

    # Si ANALIZADOR_TOKEN está definido, se exige en todas las rutas salvo /salud.
    # Se acepta como cabecera "Authorization: Bearer <token>" o, desde el navegador,
    # abriendo una vez la URL con ?token=<token>, que lo guarda en una cookie HttpOnly.
    def autenticar(self, url, ruta, query):
        if not TOKEN or ruta == "/salud":
            return True

        if tokenValido(query.get("token", [""])[0]):
            resto = urlencode({k: v for k, v in query.items() if k != "token"}, doseq=True)
            self.responder(HTTPStatus.SEE_OTHER, b"", "text/plain", {
                "Set-Cookie": f"{COOKIE}={TOKEN}; Path=/; HttpOnly; SameSite=Strict",
                "Location": url.path + (f"?{resto}" if resto else ""),
            })
            return False

        cabecera = self.headers.get("Authorization", "")
        bearer = cabecera[7:] if cabecera.startswith("Bearer ") else ""
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            cookie = cookies[COOKIE].value if COOKIE in cookies else ""
        except CookieError:
            cookie = ""
        if tokenValido(bearer) or tokenValido(cookie):
            return True

        accept = self.headers.get("Accept", "")
        if "text/html" in accept and "application/json" not in accept:
            self.responder(HTTPStatus.UNAUTHORIZED, PAGINA_TOKEN.encode(), "text/html; charset=utf-8")
        else:
            self.responderJson(HTTPStatus.UNAUTHORIZED, {"error": "Token de acceso requerido"})
        return False

    def servirEstatico(self, ruta):
        # Ficheros del frontend; cualquier otra ruta devuelve index.html para que la resuelva Angular
        relativa = os.path.normpath(ruta.lstrip("/")) if ruta != "/" else "index.html"
        fichero = os.path.join(PUBLICO, relativa)
        oculto = any(parte.startswith(".") for parte in relativa.split(os.sep))
        if oculto or not os.path.realpath(fichero).startswith(os.path.realpath(PUBLICO) + os.sep) or not os.path.isfile(fichero):
            fichero = os.path.join(PUBLICO, "index.html")
        tipo = mimetypes.guess_type(fichero)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo == "application/javascript":
            tipo += "; charset=utf-8"
        with open(fichero, "rb") as f:
            self.responder(HTTPStatus.OK, f.read(), tipo)

    def responderJson(self, estado, datos):
        self.responder(estado, json.dumps(datos, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def responder(self, estado, contenido, tipo, extra=None):
        self.send_response(estado)
        for clave, valor in {**CABECERAS_SEGURIDAD, **(extra or {})}.items():
            self.send_header(clave, valor)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(contenido)))
        self.end_headers()
        if self.enviar_cuerpo:
            self.wfile.write(contenido)

    def do_POST(self):
        self.enviar_cuerpo = True
        self.responderJson(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "Método no permitido"})

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_POST

if __name__ == "__main__":
    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/javascript", ".mjs")
    servidor = ThreadingHTTPServer(("0.0.0.0", PUERTO), Manejador)
    servidor.daemon_threads = True
    print(f"Servidor escuchando en puerto {PUERTO}", flush=True)
    if not TOKEN:
        print("AVISO: la API no tiene token de acceso. Publica el puerto solo en 127.0.0.1 o define ANALIZADOR_TOKEN.", flush=True)
    servidor.serve_forever()
