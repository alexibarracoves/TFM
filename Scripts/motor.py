import os
import docker

# Sockets por defecto de Docker y Podman. Podman expone en el suyo una API compatible con Docker,
# así que el mismo cliente sirve para los dos motores.
SOCKETS = ["/var/run/docker.sock", "/run/podman/podman.sock"]

# Capacidades que concede Docker por defecto (moby/oci/caps/defaults.go)
CAPS_DOCKER_DEFECTO = [
    "CAP_CHOWN", "CAP_DAC_OVERRIDE", "CAP_FSETID", "CAP_FOWNER", "CAP_MKNOD",
    "CAP_NET_RAW", "CAP_SETGID", "CAP_SETUID", "CAP_SETFCAP", "CAP_SETPCAP",
    "CAP_NET_BIND_SERVICE", "CAP_SYS_CHROOT", "CAP_KILL", "CAP_AUDIT_WRITE"
]

CAPS_TODAS = [
    "CAP_CHOWN", "CAP_DAC_OVERRIDE", "CAP_DAC_READ_SEARCH", "CAP_FOWNER", "CAP_FSETID",
    "CAP_KILL", "CAP_SETGID", "CAP_SETUID", "CAP_SETPCAP", "CAP_LINUX_IMMUTABLE",
    "CAP_NET_BIND_SERVICE", "CAP_NET_BROADCAST", "CAP_NET_ADMIN", "CAP_NET_RAW",
    "CAP_IPC_LOCK", "CAP_IPC_OWNER", "CAP_SYS_MODULE", "CAP_SYS_RAWIO", "CAP_SYS_CHROOT",
    "CAP_SYS_PTRACE", "CAP_SYS_PACCT", "CAP_SYS_ADMIN", "CAP_SYS_BOOT", "CAP_SYS_NICE",
    "CAP_SYS_RESOURCE", "CAP_SYS_TIME", "CAP_SYS_TTY_CONFIG", "CAP_MKNOD", "CAP_LEASE",
    "CAP_AUDIT_WRITE", "CAP_AUDIT_CONTROL", "CAP_SETFCAP", "CAP_MAC_OVERRIDE",
    "CAP_MAC_ADMIN", "CAP_SYSLOG", "CAP_WAKE_ALARM", "CAP_BLOCK_SUSPEND", "CAP_AUDIT_READ",
    "CAP_PERFMON", "CAP_BPF", "CAP_CHECKPOINT_RESTORE"
]

def _detectar_host():
    if os.environ.get("DOCKER_HOST"):
        return os.environ["DOCKER_HOST"]
    for ruta in SOCKETS:
        if os.path.exists(ruta):
            return f"unix://{ruta}"
    raise RuntimeError(
        f"No se encontró el socket del motor de contenedores. Monta uno en {' o '.join(SOCKETS)} "
        "o indica su ruta con la variable DOCKER_HOST."
    )

# Se exporta DOCKER_HOST para que Trivy use el mismo motor y pueda escanear imágenes locales
os.environ["DOCKER_HOST"] = _detectar_host()
cliente = docker.from_env()

_version = cliente.version()
ES_PODMAN = any("podman" in c.get("Name", "").lower() for c in _version.get("Components", []))
NOMBRE = "podman" if ES_PODMAN else "docker"

def _libpod(ruta):
    # La API nativa de Podman da datos que la compatible con Docker no incluye (capacidades efectivas, rootless).
    # Solo responde en rutas con versión, así que se usa la del propio motor.
    url = f"{cliente.api.base_url}/v{_version['Version']}/libpod{ruta}"
    return cliente.api._result(cliente.api._get(url), json=True)

def modoRoot():
    if ES_PODMAN:
        return not _libpod("/info").get("host", {}).get("security", {}).get("rootless", False)
    return "name=rootless" not in cliente.info().get("SecurityOptions", [])

def listarContenedores():
    return cliente.api.containers()

def _normalizarCap(cap):
    cap = cap.upper()
    return cap if cap.startswith("CAP_") else f"CAP_{cap}"

def _capacidadesDocker(datos):
    host_config = datos.get("HostConfig", {})
    if host_config.get("Privileged"):
        return list(CAPS_TODAS)
    anadidas = [_normalizarCap(c) for c in host_config.get("CapAdd") or []]
    quitadas = [_normalizarCap(c) for c in host_config.get("CapDrop") or []]
    caps = set(CAPS_TODAS if "CAP_ALL" in anadidas else CAPS_DOCKER_DEFECTO) | set(anadidas)
    if "CAP_ALL" in quitadas:
        caps = set(anadidas)
    caps -= set(quitadas)
    caps.discard("CAP_ALL")
    return sorted(caps)

def inspeccionar(id):
    datos = cliente.api.inspect_container(id)
    if ES_PODMAN:
        capacidades = _libpod(f"/containers/{id}/json").get("EffectiveCaps") or []
    else:
        capacidades = _capacidadesDocker(datos)
    return {
        "nombre": datos["Name"].lstrip("/"),
        "estado": datos.get("State", {}).get("Status", "desconocido"),
        "capacidades": capacidades,
        "puertos": datos.get("NetworkSettings", {}).get("Ports") or {},
        "redes": datos.get("NetworkSettings", {}).get("Networks") or {}
    }

def logs(nombre, num_lineas):
    salida = cliente.api.logs(nombre, timestamps=True, tail=num_lineas)
    return salida.decode("utf-8", errors="replace").splitlines()
